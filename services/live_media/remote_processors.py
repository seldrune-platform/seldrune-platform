"""Processors that dispatch authorized transforms to cloud GPU workers."""

from dataclasses import dataclass, field
from uuid import uuid4

from .processors import AudioProcessor, MediaFrame, VideoProcessor
from .worker_pool import WorkerPool
from .worker_protocol import InferenceRequest, MediaKind


def _session_profile(configured: str, requested: str) -> str:
    """Require the pipeline profile to match the worker ticket's session binding."""
    if not configured or not requested:
        raise ValueError("authorized session profile is required")
    if requested != configured:
        raise ValueError("profile does not match the session-bound profile")
    return configured


@dataclass
class RemoteVideoProcessor(VideoProcessor):
    pool: WorkerPool
    session_id: str
    profile_id: str
    region: str
    width: int = 1920
    height: int = 1080
    fps: int = 30
    sequence: int = field(default=0, init=False)

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        bound_profile = _session_profile(self.profile_id, profile_id)
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.VIDEO,
            profile_id=bound_profile,
            timestamp_ms=frame.timestamp_ms,
            payload=frame.payload,
            sequence=self.sequence,
            width=self.width,
            height=self.height,
            fps=self.fps,
        )
        self.sequence += 1
        result = await self.pool.infer(request, self.region)
        return MediaFrame(result.payload, result.timestamp_ms)


@dataclass
class RemoteAudioProcessor(AudioProcessor):
    pool: WorkerPool
    session_id: str
    profile_id: str
    region: str
    sample_rate_hz: int = 48000
    channels: int = 1
    sequence: int = field(default=0, init=False)

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        bound_profile = _session_profile(self.profile_id, profile_id)
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.AUDIO,
            profile_id=bound_profile,
            timestamp_ms=frame.timestamp_ms,
            payload=frame.payload,
            sequence=self.sequence,
            sample_rate_hz=self.sample_rate_hz,
            channels=self.channels,
        )
        self.sequence += 1
        result = await self.pool.infer(request, self.region)
        return MediaFrame(result.payload, result.timestamp_ms)
