import asyncio

import pytest

from services.live_media.pipeline import LivePipeline
from services.live_media.processors import MediaFrame
from services.live_media.remote_processors import (
    RemoteAudioProcessor,
    RemoteVideoProcessor,
)
from services.live_media.worker_protocol import InferenceRequest, InferenceResult, MediaKind


class RecordingWorkerPool:
    def __init__(self) -> None:
        self.calls: list[tuple[InferenceRequest, str]] = []

    async def infer(self, request: InferenceRequest, region: str) -> InferenceResult:
        self.calls.append((request, region))
        return InferenceResult(
            request_id=request.request_id,
            timestamp_ms=request.timestamp_ms,
            payload=b"transformed:" + request.payload,
            inference_ms=1.0,
        )


def test_live_pipeline_dispatches_bound_video_and_audio_profiles() -> None:
    async def scenario() -> None:
        pool = RecordingWorkerPool()
        pipeline = LivePipeline(
            video=RemoteVideoProcessor(
                pool=pool,
                session_id="session-1",
                profile_id="face-profile-1",
                region="us-east",
            ),
            audio=RemoteAudioProcessor(
                pool=pool,
                session_id="session-1",
                profile_id="voice-profile-1",
                region="us-east",
            ),
            face_profile_id="face-profile-1",
            voice_profile_id="voice-profile-1",
        )

        video = await pipeline.video_frame(MediaFrame(b"video-frame", 1000))
        audio = await pipeline.audio_frame(MediaFrame(b"audio-frame", 1010))

        assert video == MediaFrame(b"transformed:video-frame", 1000)
        assert audio == MediaFrame(b"transformed:audio-frame", 1010)
        assert pipeline.sync is not None
        assert pipeline.sync.video_ts_ms == 1000
        assert pipeline.sync.audio_ts_ms == 1010

        video_request, video_region = pool.calls[0]
        audio_request, audio_region = pool.calls[1]
        assert video_region == audio_region == "us-east"
        assert video_request.media_kind == MediaKind.VIDEO
        assert video_request.profile_id == "face-profile-1"
        assert (video_request.width, video_request.height, video_request.fps) == (
            1920,
            1080,
            30,
        )
        assert audio_request.media_kind == MediaKind.AUDIO
        assert audio_request.profile_id == "voice-profile-1"
        assert (audio_request.sample_rate_hz, audio_request.channels) == (48000, 1)

    asyncio.run(scenario())


@pytest.mark.parametrize("processor_kind", ["video", "audio"])
def test_remote_processor_rejects_profile_outside_session_binding(
    processor_kind: str,
) -> None:
    async def scenario() -> None:
        pool = RecordingWorkerPool()
        processor = (
            RemoteVideoProcessor(
                pool=pool,
                session_id="session-1",
                profile_id="face-profile-1",
                region="us-east",
            )
            if processor_kind == "video"
            else RemoteAudioProcessor(
                pool=pool,
                session_id="session-1",
                profile_id="voice-profile-1",
                region="us-east",
            )
        )

        with pytest.raises(ValueError, match="session-bound"):
            await processor.process(MediaFrame(b"frame", 1000), "other-profile")

        assert pool.calls == []
        assert processor.sequence == 0

    asyncio.run(scenario())
