"""Collect real files and measured metrics into a Face verification receipt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.live_media.face_inference_evidence import FaceInferenceEvidence
from services.live_media.face_output_manifest import FaceOutputManifest
from services.live_media.face_stream_gate import FaceStreamEvidence
from services.live_media.face_training_executor import sha256_file
from services.live_media.face_verification_receipt import FaceVerificationReceipt


@dataclass(frozen=True)
class FaceEvidenceFiles:
    checkpoint: Path
    onnx_model: Path
    input_frame: Path
    output_frame: Path
    reference_image: Path

    def validate(self) -> None:
        for path in (
            self.checkpoint,
            self.onnx_model,
            self.input_frame,
            self.output_frame,
            self.reference_image,
        ):
            if not path.is_file():
                raise ValueError(f"evidence file is missing: {path.name}")
            if path.stat().st_size < 1:
                raise ValueError(f"evidence file is empty: {path.name}")


@dataclass(frozen=True)
class FaceMeasuredMetrics:
    inference_ms: float
    identity_similarity: float
    frame_change_ratio: float
    frames_processed: int
    frames_transformed: int
    stream_duration_seconds: float
    average_inference_ms: float
    authorization_verified: bool
    synthetic_media_indicator_verified: bool


def collect_verification_receipt(
    *,
    run_id: str,
    model_version: str,
    dataset_manifest_sha256: str,
    files: FaceEvidenceFiles,
    metrics: FaceMeasuredMetrics,
) -> FaceVerificationReceipt:
    """Hash supplied evidence files and validate the resulting receipt."""
    files.validate()
    checkpoint_sha256 = sha256_file(files.checkpoint)
    onnx_sha256 = sha256_file(files.onnx_model)
    receipt = FaceVerificationReceipt(
        run_id=run_id,
        output=FaceOutputManifest(
            model_version=model_version,
            checkpoint_sha256=checkpoint_sha256,
            dataset_manifest_sha256=dataset_manifest_sha256,
            onnx_sha256=onnx_sha256,
        ),
        inference=FaceInferenceEvidence(
            model_sha256=onnx_sha256,
            input_sha256=sha256_file(files.input_frame),
            output_sha256=sha256_file(files.output_frame),
            inference_ms=metrics.inference_ms,
        ),
        stream=FaceStreamEvidence(
            frames_processed=metrics.frames_processed,
            frames_transformed=metrics.frames_transformed,
            duration_seconds=metrics.stream_duration_seconds,
            average_inference_ms=metrics.average_inference_ms,
        ),
        reference_sha256=sha256_file(files.reference_image),
        identity_similarity=metrics.identity_similarity,
        frame_change_ratio=metrics.frame_change_ratio,
        authorization_verified=metrics.authorization_verified,
        synthetic_media_indicator_verified=metrics.synthetic_media_indicator_verified,
    )
    receipt.validate()
    return receipt
