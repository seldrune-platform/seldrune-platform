import asyncio

from services.live_media.gpu_scheduler import GPUWorker
from services.live_media.processors import MediaFrame
from services.live_media.remote_processors import (
    RemoteAudioProcessor,
    RemoteVideoProcessor,
)
from services.live_media.worker_pool import WorkerPool
from services.live_media.worker_protocol import InferenceResult, MediaKind


def test_remote_video_dispatches_to_gpu_pool():
    seen = []

    async def call(worker, request):
        seen.append((worker.worker_id, request.media_kind))
        return InferenceResult(
            request.request_id,
            request.timestamp_ms,
            b"video-out",
            10.0,
        )

    processor = RemoteVideoProcessor(
        WorkerPool([GPUWorker("gpu-1", "in")], call),
        "session-1",
        "face-1",
        "in",
    )
    result = asyncio.run(processor.process(MediaFrame(b"video", 100)))
    assert result.payload == b"video-out"
    assert seen == [("gpu-1", MediaKind.VIDEO)]


def test_remote_audio_dispatches_to_gpu_pool():
    async def call(worker, request):
        return InferenceResult(
            request.request_id,
            request.timestamp_ms,
            b"audio-out",
            8.0,
        )

    processor = RemoteAudioProcessor(
        WorkerPool([GPUWorker("gpu-1", "in")], call),
        "session-1",
        "voice-1",
        "in",
    )
    result = asyncio.run(processor.process(MediaFrame(b"audio", 101)))
    assert result.payload == b"audio-out"
