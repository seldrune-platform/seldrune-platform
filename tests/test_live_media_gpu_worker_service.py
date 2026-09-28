import asyncio

from services.live_media.gpu_worker_service import GPUWorkerService
from services.live_media.processors import MediaFrame
from services.live_media.worker_protocol import InferenceRequest, MediaKind


class _Face:
    async def transform_video(self, frame, profile_id):
        await asyncio.sleep(0.002)
        return MediaFrame(b"video-output", frame.timestamp_ms)


class _Voice:
    async def transform_audio(self, frame, profile_id):
        await asyncio.sleep(0.002)
        return MediaFrame(b"audio-output", frame.timestamp_ms)


def test_gpu_worker_reports_measured_processing_duration():
    service = GPUWorkerService(face=_Face(), voice=_Voice())
    video = asyncio.run(
        service.infer(
            InferenceRequest(
                request_id="video-1",
                session_id="session-1",
                media_kind=MediaKind.VIDEO,
                profile_id="face-profile",
                timestamp_ms=1200,
                payload=b"video-input",
            )
        )
    )
    audio = asyncio.run(
        service.infer(
            InferenceRequest(
                request_id="audio-1",
                session_id="session-1",
                media_kind=MediaKind.AUDIO,
                profile_id="voice-profile",
                timestamp_ms=1230,
                payload=b"audio-input",
            )
        )
    )
    assert video.payload == b"video-output"
    assert audio.payload == b"audio-output"
    assert video.inference_ms > 0
    assert audio.inference_ms > 0

