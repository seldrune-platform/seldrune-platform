"""Release gate for promoting Face v0.1 from training evidence to LiveShift."""
from dataclasses import dataclass

from services.live_media.face_output_gate import FaceOutputEvidence


@dataclass(frozen=True)
class FaceReleaseGate:
    output: FaceOutputEvidence
    continuous_stream_verified: bool
    authorized_profile_verified: bool

    def validate(self) -> None:
        self.output.validate()
        if not self.authorized_profile_verified:
            raise ValueError("authorized identity profile verification is required")
        if not self.continuous_stream_verified:
            raise ValueError("continuous stream verification is required")
