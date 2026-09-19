"""Evidence gate before Seldrune reports a real Face v0.1 output."""
from dataclasses import dataclass

from services.live_media.face_artifact_manifest import FaceArtifactManifest


@dataclass(frozen=True)
class FaceOutputEvidence:
    artifact: FaceArtifactManifest
    model_loaded: bool
    transformed_frame: bool
    inference_ms: float

    def validate(self) -> None:
        self.artifact.validate()
        if not self.model_loaded:
            raise ValueError("trained model must be loaded")
        if not self.transformed_frame:
            raise ValueError("real output requires a transformed frame")
        if self.inference_ms <= 0:
            raise ValueError("inference latency must be measured")
