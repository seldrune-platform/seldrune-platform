"""Unified proof receipt for a real Seldrune Face v0.1 transformed-frame claim."""

from __future__ import annotations

import math
from dataclasses import dataclass

from services.live_media.face_inference_evidence import FaceInferenceEvidence
from services.live_media.face_output_manifest import FaceOutputManifest
from services.live_media.face_stream_gate import FaceStreamEvidence


@dataclass(frozen=True)
class FaceVerificationThresholds:
    minimum_identity_similarity: float = 0.75
    minimum_frame_change_ratio: float = 0.01
    maximum_frame_change_ratio: float = 0.95
    maximum_inference_ms: float = 100.0
    minimum_transformed_frame_ratio: float = 0.95

    def validate(self) -> None:
        unit_values = (
            self.minimum_identity_similarity,
            self.minimum_frame_change_ratio,
            self.maximum_frame_change_ratio,
            self.minimum_transformed_frame_ratio,
        )
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in unit_values):
            raise ValueError("verification ratios must be finite values between zero and one")
        if self.minimum_frame_change_ratio >= self.maximum_frame_change_ratio:
            raise ValueError("frame-change bounds are invalid")
        if not math.isfinite(self.maximum_inference_ms) or self.maximum_inference_ms <= 0:
            raise ValueError("maximum inference latency must be positive")


@dataclass(frozen=True)
class FaceVerificationReceipt:
    run_id: str
    output: FaceOutputManifest
    inference: FaceInferenceEvidence
    stream: FaceStreamEvidence
    reference_sha256: str
    identity_similarity: float
    frame_change_ratio: float
    authorization_verified: bool
    synthetic_media_indicator_verified: bool

    def validate(self, thresholds: FaceVerificationThresholds | None = None) -> None:
        """Bind all measured proof to one artifact before reporting real output."""
        limits = thresholds or FaceVerificationThresholds()
        limits.validate()
        self.output.validate()
        self.inference.validate()
        self.stream.validate()
        if not self.run_id.strip():
            raise ValueError("verification run identity is required")
        if len(self.reference_sha256) != 64:
            raise ValueError("reference-image SHA-256 evidence is required")
        if self.output.onnx_sha256 is None:
            raise ValueError("verified transformed output requires an ONNX artifact")
        if self.inference.model_sha256 != self.output.onnx_sha256:
            raise ValueError("inference model does not match the output manifest")
        if not math.isfinite(self.identity_similarity):
            raise ValueError("identity similarity must be finite")
        if self.identity_similarity < limits.minimum_identity_similarity:
            raise ValueError("identity similarity is below the verification threshold")
        if not math.isfinite(self.frame_change_ratio):
            raise ValueError("frame-change ratio must be finite")
        frame_change_in_bounds = (
            limits.minimum_frame_change_ratio
            <= self.frame_change_ratio
            <= limits.maximum_frame_change_ratio
        )
        if not frame_change_in_bounds:
            raise ValueError("frame-change ratio is outside verification bounds")
        if self.inference.inference_ms > limits.maximum_inference_ms:
            raise ValueError("single-frame inference latency exceeds the verification budget")
        transformed_ratio = self.stream.frames_transformed / self.stream.frames_processed
        if transformed_ratio < limits.minimum_transformed_frame_ratio:
            raise ValueError("continuous transformed-frame ratio is below threshold")
        if not self.authorization_verified:
            raise ValueError("authorized identity verification is required")
        if not self.synthetic_media_indicator_verified:
            raise ValueError("synthetic-media indicator verification is required")


def verify_real_output(
    receipt: FaceVerificationReceipt,
    thresholds: FaceVerificationThresholds | None = None,
) -> FaceVerificationReceipt:
    """Return the receipt only after every real-output proof gate succeeds."""
    receipt.validate(thresholds)
    return receipt
