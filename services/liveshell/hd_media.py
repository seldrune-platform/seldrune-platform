"""Evidence-gated HD media targets for Seldrune LiveShell."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HDVideoTarget:
    width: int = 1280
    height: int = 720
    fps: int = 30

    def validate(self) -> None:
        if self.width < 1280 or self.height < 720:
            raise ValueError("LiveShell HD video requires at least 1280x720")
        if self.fps < 24:
            raise ValueError("LiveShell HD video requires at least 24 fps")


@dataclass(frozen=True)
class HDVoiceTarget:
    sample_rate: int = 48000
    channels: int = 1

    def validate(self) -> None:
        if self.sample_rate < 48000:
            raise ValueError("LiveShell HD voice requires at least 48 kHz")
        if self.channels not in (1, 2):
            raise ValueError("LiveShell voice supports mono or stereo")


@dataclass(frozen=True)
class MobileLatencyBudget:
    glass_to_glass_ms: int = 250
    av_drift_ms: int = 80


@dataclass(frozen=True)
class LiveShellRuntimeEvidence:
    hd_video_returned: bool = False
    hd_audio_returned: bool = False
    av_sync_verified: bool = False
    mobile_session_verified: bool = False

    @property
    def hd_mobile_ready(self) -> bool:
        return all(
            (
                self.hd_video_returned,
                self.hd_audio_returned,
                self.av_sync_verified,
                self.mobile_session_verified,
            )
        )
