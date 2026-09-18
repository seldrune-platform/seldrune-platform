"""Processors that dispatch authorized transforms to cloud GPU workers."""
from dataclasses import dataclass
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

    async def process(self, frame: MediaFrame) -> MediaFrame:
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.VIDEO,
            profile_id=self.profile_id,
            timestamp_ms=frame.timestamp_ms,
            payload=frame.payload,
        )
        result = await self.pool.infer(request, self.region)
        return MediaFrame(result.payload, result.timestamp_ms)


@dataclass
class RemoteAudioProcessor(AudioProcessor):
    pool: WorkerPool
    session_id: str
    profile_id: str
    region: str

    async def process(self, frame: MediaFrame) -> MediaFrame:
        request = InferenceRequest(
            request_id=str(uuid4()),
            session_id=self.session_id,
            media_kind=MediaKind.AUDIO,
            profile_id=self.profile_id,
            timestamp_ms=frame.timestamp_ms,
            payload=frame.payload,
        )
        result = await self.pool.infer(request, self.region)
        return MediaFrame(result.payload, result.timestamp_ms)
