"""Combined mobile HD A/V runtime and evidence gate for LiveShell."""

from __future__ import annotations

from dataclasses import dataclass

from services.live_media.processors import MediaFrame

from .hd_media import LiveShellRuntimeEvidence, MobileLatencyBudget
from .hd_video_runtime import LiveShellHDVideoProcessor
from .hd_voice_runtime import LiveShellHDVoiceProcessor


@dataclass(frozen=True)
class LiveShellMobileMetrics:
    video_latency_ms: int
    audio_latency_ms: int
    av_drift_ms: int
    mobile_session_verified: bool

    def evidence(self, budget: MobileLatencyBudget) -> LiveShellRuntimeEvidence:
        return LiveShellRuntimeEvidence(
            hd_video_returned=self.video_latency_ms <= budget.glass_to_glass_ms,
            hd_audio_returned=self.audio_latency_ms <= budget.glass_to_glass_ms,
            av_sync_verified=abs(self.av_drift_ms) <= budget.av_drift_ms,
            mobile_session_verified=self.mobile_session_verified,
        )


@dataclass
class LiveShellMobileAVPipeline:
    video: LiveShellHDVideoProcessor
    audio: LiveShellHDVoiceProcessor
    budget: MobileLatencyBudget = MobileLatencyBudget()

    async def process_video(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        return await self.video.process(frame, profile_id)

    async def process_audio(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        return await self.audio.process(frame, profile_id)

    def capture_evidence(
        self,
        *,
        video_latency_ms: int,
        audio_latency_ms: int,
        video_timestamp_ms: int,
        audio_timestamp_ms: int,
        mobile_session_verified: bool,
    ) -> LiveShellRuntimeEvidence:
        metrics = LiveShellMobileMetrics(
            video_latency_ms=video_latency_ms,
            audio_latency_ms=audio_latency_ms,
            av_drift_ms=video_timestamp_ms - audio_timestamp_ms,
            mobile_session_verified=mobile_session_verified,
        )
        return metrics.evidence(self.budget)
