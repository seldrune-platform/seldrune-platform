import asyncio

from services.live_media.processors import MediaFrame
from services.liveshell.hd_video_runtime import LiveShellHDVideoProcessor
from services.liveshell.hd_voice_runtime import LiveShellHDVoiceProcessor
from services.liveshell.mobile_av_pipeline import LiveShellMobileAVPipeline
from services.liveshell.mobile_webrtc_session import LiveShellMobileSession


class HDFrame:
    shape = (720, 1280, 3)


def test_mobile_session_routes_authorized_profiles_and_records_latency():
    seen = []

    async def transform(payload, reference):
        seen.append(reference)
        return payload

    pipeline = LiveShellMobileAVPipeline(
        video=LiveShellHDVideoProcessor(
            transform=transform, reference_provider=lambda p: f"face:{p}"
        ),
        audio=LiveShellHDVoiceProcessor(
            transform=transform, reference_provider=lambda p: f"voice:{p}"
        ),
    )
    session = LiveShellMobileSession(
        pipeline, "face-authorized", "voice-authorized", mobile_client_verified=True
    )
    video, video_latency = asyncio.run(
        session.video_frame(MediaFrame(HDFrame(), 1000))
    )
    audio, audio_latency = asyncio.run(
        session.audio_frame(MediaFrame(b"audio", 1030))
    )
    assert seen == ["face:face-authorized", "voice:voice-authorized"]
    assert video.timestamp_ms == 1000
    assert audio.timestamp_ms == 1030
    assert video_latency >= 0
    assert audio_latency >= 0
    evidence = session.evidence(
        video_latency_ms=video_latency,
        audio_latency_ms=audio_latency,
        video_timestamp_ms=video.timestamp_ms,
        audio_timestamp_ms=audio.timestamp_ms,
    )
    assert evidence.hd_mobile_ready


def test_mobile_session_does_not_self_attest_real_client():
    async def transform(payload, reference):
        return payload

    pipeline = LiveShellMobileAVPipeline(
        video=LiveShellHDVideoProcessor(
            transform=transform, reference_provider=lambda _: "face"
        ),
        audio=LiveShellHDVoiceProcessor(
            transform=transform, reference_provider=lambda _: "voice"
        ),
    )
    session = LiveShellMobileSession(pipeline, "face", "voice")
    evidence = session.evidence(
        video_latency_ms=1,
        audio_latency_ms=1,
        video_timestamp_ms=1000,
        audio_timestamp_ms=1000,
    )
    assert not evidence.mobile_session_verified
    assert not evidence.hd_mobile_ready
