"""Health signals for real-time media sessions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamHealth:
    rtt_ms: float
    packet_loss: float
    video_inference_ms: float
    audio_inference_ms: float
    av_drift_ms: float

    @property
    def healthy(self) -> bool:
        return (
            self.rtt_ms < 250
            and self.packet_loss < 0.08
            and self.video_inference_ms < 80
            and self.audio_inference_ms < 60
            and abs(self.av_drift_ms) < 100
        )
