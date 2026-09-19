import asyncio
import sys
import types

import pytest

from services.live_media.av_video_codec import (
    decode_av_video_frame,
    encode_av_video_frame,
)
from services.live_media.processors import MediaFrame


np = pytest.importorskip("numpy")


class _InputFrame:
    time = 1.25
    pts = 90
    time_base = "1/30"

    def to_ndarray(self, format):
        assert format == "rgb24"
        return np.full((256, 256, 3), 128, dtype=np.uint8)


class _OutputFrame:
    def __init__(self, array):
        self.array = array
        self.pts = None
        self.time_base = None


class _VideoFrame:
    @staticmethod
    def from_ndarray(array, format):
        assert format == "rgb24"
        return _OutputFrame(array)


@pytest.fixture(autouse=True)
def fake_av(monkeypatch):
    module = types.ModuleType("av")
    module.VideoFrame = _VideoFrame
    monkeypatch.setitem(sys.modules, "av", module)


def test_decode_av_video_frame_produces_face_tensor():
    result = asyncio.run(decode_av_video_frame(_InputFrame()))

    assert result.payload.shape == (1, 3, 256, 256)
    assert result.payload.dtype == np.float32
    assert result.timestamp_ms == 1250
    assert np.isclose(result.payload.mean(), 128 / 255.0)


def test_encode_av_video_frame_preserves_timing():
    original = _InputFrame()
    tensor = np.full((1, 3, 256, 256), 0.5, dtype=np.float32)

    result = asyncio.run(
        encode_av_video_frame(
            MediaFrame(payload=tensor, timestamp_ms=1250),
            original,
        )
    )

    assert result.array.shape == (256, 256, 3)
    assert result.array.dtype == np.uint8
    assert result.pts == 90
    assert result.time_base == "1/30"
