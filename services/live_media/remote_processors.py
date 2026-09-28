"""Processors that dispatch authorized transforms to cloud GPU workers."""

from dataclasses import dataclass, field
from uuid import uuid4

from .processors import AudioProcessor, MediaFrame, VideoProcessor
from .worker_pool import WorkerPool
from .worker_protocol import InferenceRequest, MediaKind


def _session_profile(configured: str, requested: str | None) -> str:
    """Require an explicit pipeline profile to match the session binding."""
    if not configured:
        raise ValueError("authorized session profile is required")
    if requested is None:
        return configured
    if not requested:
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
    fps: float = 30.0
    sequence: int = field(default=0, init=False)

    async def process(
        self, frame: MediaFrame, profile_id: str | None = None
    ) -> MediaFrame:
        bound_profile = _session_profile(self.profile_id, profile_id)
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.VIDEO,
            profile_id=bound_profile,
            timestamp_ms=frame.timestamp_ms,
            payload=frame.payload,
            sequence=self.sequence,
            width=frame.width if frame.width is not None else self.width,
            height=frame.height if frame.height is not None else self.height,
            fps=frame.fps if frame.fps is not None else self.fps,
            pixel_format=frame.pixel_format,
        )
        self.sequence += 1
        result = await self.pool.infer(request, self.region)
        return MediaFrame(
            result.payload,
            result.timestamp_ms,
            width=result.width if result.width is not None else frame.width,
            height=result.height if result.height is not None else frame.height,
            fps=result.fps if result.fps is not None else frame.fps,
            pixel_format=result.pixel_format or frame.pixel_format,
            sample_rate_hz=(
                result.sample_rate_hz
                if result.sample_rate_hz is not None
                else frame.sample_rate_hz
            ),
            channels=result.channels if result.channels is not None else frame.channels,
        )


@dataclass
class RemoteAudioProcessor(AudioProcessor):
    pool: WorkerPool
    session_id: str
    profile_id: str
    region: str
    sample_rate_hz: int = 48000
    channels: int = 1
    sequence: int = field(default=0, init=False)

    async def process(
        self, frame: MediaFrame, profile_id: str | None = None
    ) -> MediaFrame:
        bound_profile = _session_profile(self.profile_id, profile_id)
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.AUDIO,
            profile_id=bound_profile,
            timestamp_ms=frame.timestamp_ms,
            payload=frame.payload,
            sequence=self.sequence,
            sample_rate_hz=(
                frame.sample_rate_hz
                if frame.sample_rate_hz is not None
                else self.sample_rate_hz
            ),
            channels=frame.channels if frame.channels is not None else self.channels,
        )
        self.sequence += 1
        result = await self.pool.infer(request, self.region)
        return MediaFrame(
            result.payload,
            result.timestamp_ms,
            width=result.width if result.width is not None else frame.width,
            height=result.height if result.height is not None else frame.height,
            fps=result.fps if result.fps is not None else frame.fps,
            sample_rate_hz=(
                result.sample_rate_hz
                if result.sample_rate_hz is not None
                else frame.sample_rate_hz
            ),
            channels=result.channels if result.channels is not None else frame.channels,
        )
