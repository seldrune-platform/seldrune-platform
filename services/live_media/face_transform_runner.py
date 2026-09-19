"""Execution boundary for authorized Seldrune Face frame transformation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol

from services.live_media.face_inference_evidence import FaceInferenceEvidence
from services.live_media.face_training_executor import sha256_file


class FaceTransformBackend(Protocol):
    def transform(self, source_frame: bytes, reference_image: bytes) -> bytes: ...


@dataclass(frozen=True)
class FaceTransformRequest:
    model_path: Path
    source_frame_path: Path
    reference_image_path: Path
    output_frame_path: Path
    authorization_verified: bool
    synthetic_media_indicator_enabled: bool

    def validate(self) -> None:
        for path in (self.model_path, self.source_frame_path, self.reference_image_path):
            if not path.is_file() or path.stat().st_size < 1:
                raise ValueError(f"required transform input is missing or empty: {path.name}")
        if self.output_frame_path in {
            self.model_path,
            self.source_frame_path,
            self.reference_image_path,
        }:
            raise ValueError("output path must not overwrite transform inputs")
        if not self.authorization_verified:
            raise ValueError("authorized identity verification is required")
        if not self.synthetic_media_indicator_enabled:
            raise ValueError("synthetic-media indicator must be enabled")


@dataclass(frozen=True)
class FaceTransformResult:
    evidence: FaceInferenceEvidence
    reference_sha256: str
    output_path: Path


def run_face_transform(
    request: FaceTransformRequest,
    backend: FaceTransformBackend,
) -> FaceTransformResult:
    """Run one authorized transform and persist only a non-empty changed frame."""
    request.validate()
    source = request.source_frame_path.read_bytes()
    reference = request.reference_image_path.read_bytes()
    started = perf_counter()
    output = backend.transform(source, reference)
    inference_ms = (perf_counter() - started) * 1000
    if not isinstance(output, bytes) or not output:
        raise ValueError("transform backend must return non-empty frame bytes")
    if output == source:
        raise ValueError("transform backend returned an unchanged frame")
    request.output_frame_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = request.output_frame_path.with_suffix(request.output_frame_path.suffix + ".tmp")
    temporary.write_bytes(output)
    temporary.replace(request.output_frame_path)
    evidence = FaceInferenceEvidence(
        model_sha256=sha256_file(request.model_path),
        input_sha256=sha256_file(request.source_frame_path),
        output_sha256=sha256_file(request.output_frame_path),
        inference_ms=max(inference_ms, 0.001),
    )
    evidence.validate()
    return FaceTransformResult(
        evidence=evidence,
        reference_sha256=sha256_file(request.reference_image_path),
        output_path=request.output_frame_path,
    )
