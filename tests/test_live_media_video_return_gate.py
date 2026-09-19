import asyncio

from services.live_media.pipeline import LivePipeline
from services.live_media.processors import (
    MediaFrame,
    PassthroughAudioProcessor,
    VideoProcessor,
)
from services.live_media.transport import MediaTransport
from services.live_media.video_return_gate import run_video_return_gate


class _Transform(VideoProcessor):
    async def process(self, frame, profile_id):
        return MediaFrame(frame.payload + b":transformed", frame.timestamp_ms)


class _Transport(MediaTransport):
    def __init__(self):
        self.sent = []
        self.next_frame = 0

    async def recv_video(self):
        self.next_frame += 1
        return MediaFrame(f"frame-{self.next_frame}".encode(), self.next_frame)

    async def recv_audio(self):
        raise AssertionError("video gate must not consume audio")

    async def send_video(self, frame):
        self.sent.append(frame)

    async def send_audio(self, frame):
        raise AssertionError("video gate must not send audio")

    async def close(self):
        pass


def test_video_return_gate_reports_transformed_delivery():
    transport = _Transport()
    pipeline = LivePipeline(
        video=_Transform(),
        audio=PassthroughAudioProcessor(),
        face_profile_id="authorized-profile",
    )

    evidence = asyncio.run(
        run_video_return_gate(transport, pipeline, frame_limit=3)
    )

    assert evidence.frames_received == 3
    assert evidence.frames_returned == 3
    assert evidence.transformed_frames == 3
    assert evidence.verified is True
    assert len(transport.sent) == 3


def test_video_return_gate_rejects_empty_run():
    transport = _Transport()
    pipeline = LivePipeline(
        video=_Transform(),
        audio=PassthroughAudioProcessor(),
        face_profile_id="authorized-profile",
    )

    import pytest

    with pytest.raises(ValueError, match="frame_limit"):
        asyncio.run(run_video_return_gate(transport, pipeline, frame_limit=0))
