import asyncio

from services.live_media.processors import MediaFrame
from services.liveshell.hd_video_runtime import LiveShellHDVideoProcessor
from services.liveshell.hd_voice_runtime import LiveShellHDVoiceProcessor
from services.liveshell.mobile_av_pipeline import LiveShellMobileAVPipeline


class HDFrame:
    shape = (720, 1280, 3)


def test_mobile_av_pipeline_processes_both_tracks_and_gates_evidence():
    async def video_transform(payload, reference):
        return payload

    async def audio_transform(payload, reference):
        return payload

    pipeline = LiveShellMobileAVPipeline(
        video=LiveShellHDVideoProcessor(
            transform=video_transform, reference_provider=lambda _: "face-ref"
        ),
        audio=LiveShellHDVoiceProcessor(
            transform=audio_transform, reference_provider=lambda _: "voice-ref"
        ),
    )

    video = asyncio.run(
        pipeline.process_video(MediaFrame(HDFrame(), 1000), "face-profile")
    )
    audio = asyncio.run(
        pipeline.process_audio(MediaFrame(b"audio", 1030), "voice-profile")
    )
    assert video.timestamp_ms == 1000
    assert audio.timestamp_ms == 1030

    evidence = pipeline.capture_evidence(
        video_latency_ms=120,
        audio_latency_ms=90,
        video_timestamp_ms=video.timestamp_ms,
        audio_timestamp_ms=audio.timestamp_ms,
        mobile_session_verified=True,
    )
    assert evidence.hd_mobile_ready


def test_mobile_av_pipeline_rejects_unverified_or_slow_session():
    async def transform(payload, reference):
        return payload

    pipeline = LiveShellMobileAVPipeline(
        video=LiveShellHDVideoProcessor(
            transform=transform, reference_provider=lambda _: "face-ref"
        ),
        audio=LiveShellHDVoiceProcessor(
            transform=transform, reference_provider=lambda _: "voice-ref"
        ),
    )
    evidence = pipeline.capture_evidence(
        video_latency_ms=300,
        audio_latency_ms=100,
        video_timestamp_ms=1000,
        audio_timestamp_ms=850,
        mobile_session_verified=False,
    )
    assert not evidence.hd_mobile_ready
    assert not evidence.hd_video_returned
    assert not evidence.av_sync_verified
