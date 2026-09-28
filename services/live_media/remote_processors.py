"""Processors that dispatch authorized transforms to cloud GPU workers."""

from dataclasses import dataclass, field
from uuid import uuid4

from .processors import AudioProcessor, MediaFrame, VideoProcessor
from .worker_pool import WorkerPool
from .worker_protocol import InferenceRequest, MediaKind


@dataclass
class RemoteVideoProcessor(VideoProcessor):
    pool: WorkerPool
    session_id: str
    profile_id: str
    region: str
    width: int = 1280
    height: int = 720
    fps: int = 30
    sequence: int = field(default=0, init=False)

    async def process(self, frame: MediaFrame) -> MediaFrame:
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.VIDEO,
            profile_id=self.profile_id,
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

    async def process(self, frame: MediaFrame) -> MediaFrame:
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.AUDIO,
            profile_id=self.profile_id,
            timestamp_ms=frame.timestamp_ms,
            payload=frame.payload,
            sequence=self.sequence,
            sample_rate_hz=self.sample_rate_hz,
            channels=self.channels,
        )
        self.sequence += 1
        result = await self.pool.infer(request, self.region)
        return MediaFrame(result.payload, result.timestamp_ms)
