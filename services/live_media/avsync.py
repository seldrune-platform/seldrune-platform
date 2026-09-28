from dataclasses import dataclass

from .realism_quality_gate import RealismQualityPolicy, validate_av_drift


@dataclass
class AVSyncState:
    audio_ts_ms: int = 0
    video_ts_ms: int = 0
    max_drift_ms: int = 80

    @property
    def drift_ms(self) -> int:
        return self.audio_ts_ms - self.video_ts_ms

    def correction(self) -> str:
        if abs(self.drift_ms) <= self.max_drift_ms:
            return "none"
        return "delay_video" if self.drift_ms > 0 else "delay_audio"

    def validate_realism(self, policy: RealismQualityPolicy) -> dict[str, int | float]:
        """Return measured sync evidence or fail when the deployment limit is exceeded."""
        return validate_av_drift(self.audio_ts_ms, self.video_ts_ms, policy)
