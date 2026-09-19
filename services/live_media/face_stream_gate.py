"""Continuous-stream evidence gate for LiveShift Face."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FaceStreamEvidence:
    frames_processed: int
    frames_transformed: int
    duration_seconds: float
    average_inference_ms: float

    def validate(self) -> None:
        if self.frames_processed < 2:
            raise ValueError("continuous stream requires multiple frames")
        if self.frames_transformed < 1 or self.frames_transformed > self.frames_processed:
            raise ValueError("invalid transformed-frame count")
        if self.duration_seconds <= 0 or self.average_inference_ms <= 0:
            raise ValueError("stream timing evidence is required")
