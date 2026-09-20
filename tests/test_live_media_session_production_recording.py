"""Tests for measured production recording in the live session loop."""

import asyncio

import pytest

from services.live_media.face_production_recorder import FaceProductionRecorder
from services.live_media.pipeline import LivePipeline
from services.live_media.processors import (
    MediaFrame,
    PassthroughAudioProcessor,
    PassthroughVideoProcessor,
)
from services.live_media.session_runner import run_video


class OneFrameTransport:
    def __init__(self) -> None:
        self._received = False
        self.sent: list[MediaFrame] = []

    async def recv_video(self) -> MediaFrame:
        if self._received:
            raise StopAsyncIteration
        self._received = True
        return MediaFrame(b"transformed-frame", 123)

    async def send_video(self, frame: MediaFrame) -> None:
        self.sent.append(frame)


def test_live_loop_records_only_successfully_returned_frames(tmp_path) -> None:
    receipt = tmp_path / "face-verification.json"
    receipt.write_bytes(b"verified-receipt")
    recorder = FaceProductionRecorder(
        run_id="live-session-001",
        verification_receipt_path=receipt,
        output_width=1280,
        output_height=720,
        audio_sample_rate_hz=None,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )
    transport = OneFrameTransport()
    pipeline = LivePipeline(
        video=PassthroughVideoProcessor(),
        audio=PassthroughAudioProcessor(),
    )

    with pytest.raises(StopAsyncIteration):
        asyncio.run(run_video(transport, pipeline, recorder))

    evidence = recorder.finish(
        session_duration_seconds=1.0,
        output_path=tmp_path / "face-production.json",
    )
    assert transport.sent == [MediaFrame(b"transformed-frame", 123)]
    assert evidence.frames_returned == 1
    assert evidence.p95_latency_ms > 0
