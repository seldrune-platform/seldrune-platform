"""LiveShell mobile WebRTC session evidence adapter."""

from __future__ import annotations

import time
from dataclasses import dataclass

from services.live_media.processors import MediaFrame

from .mobile_av_pipeline import LiveShellMobileAVPipeline


@dataclass
class LiveShellMobileSession:
    pipeline: LiveShellMobileAVPipeline
    face_profile_id: str
    voice_profile_id: str
    mobile_client_verified: bool = False

    async def video_frame(self, frame: MediaFrame) -> tuple[MediaFrame, int]:
        started = time.perf_counter_ns()
        output = await self.pipeline.process_video(frame, self.face_profile_id)
        latency_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
        return output, latency_ms

    async def audio_frame(self, frame: MediaFrame) -> tuple[MediaFrame, int]:
        started = time.perf_counter_ns()
        output = await self.pipeline.process_audio(frame, self.voice_profile_id)
        latency_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
        return output, latency_ms

    def evidence(
        self,
        *,
        video_latency_ms: int,
        audio_latency_ms: int,
        video_timestamp_ms: int,
        audio_timestamp_ms: int,
    ):
        return self.pipeline.capture_evidence(
            video_latency_ms=video_latency_ms,
            audio_latency_ms=audio_latency_ms,
            video_timestamp_ms=video_timestamp_ms,
            audio_timestamp_ms=audio_timestamp_ms,
            mobile_session_verified=self.mobile_client_verified,
        )
