"""Bounded continuous-frame execution for the Seldrune Face transform path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from services.live_media.face_stream_gate import FaceStreamEvidence
from services.live_media.face_transform_runner import (
    FaceTransformBackend,
    FaceTransformRequest,
    FaceTransformResult,
    run_face_transform,
)


@dataclass(frozen=True)
class FaceStreamRun:
    evidence: FaceStreamEvidence
    frames: tuple[FaceTransformResult, ...]


def run_face_stream(
    *,
    model_path: Path,
    source_frames: tuple[Path, ...],
    reference_image_path: Path,
    output_dir: Path,
    backend: FaceTransformBackend,
    authorization_verified: bool,
    synthetic_media_indicator_enabled: bool,
) -> FaceStreamRun:
    """Transform a bounded ordered frame sequence and return measured stream evidence."""
    if len(source_frames) < 2:
        raise ValueError("continuous transform requires at least two source frames")
    if len(set(source_frames)) != len(source_frames):
        raise ValueError("source frame paths must be unique")
    started = perf_counter()
    results = []
    for index, source_path in enumerate(source_frames):
        result = run_face_transform(
            FaceTransformRequest(
                model_path=model_path,
                source_frame_path=source_path,
                reference_image_path=reference_image_path,
                output_frame_path=output_dir / f"frame-{index:06d}.bin",
                authorization_verified=authorization_verified,
                synthetic_media_indicator_enabled=synthetic_media_indicator_enabled,
            ),
            backend,
        )
        results.append(result)
    duration = max(perf_counter() - started, 0.001)
    evidence = FaceStreamEvidence(
        frames_processed=len(source_frames),
        frames_transformed=len(results),
        duration_seconds=duration,
        average_inference_ms=sum(item.evidence.inference_ms for item in results) / len(results),
    )
    evidence.validate()
    return FaceStreamRun(evidence=evidence, frames=tuple(results))
