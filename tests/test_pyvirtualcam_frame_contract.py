import asyncio
import sys
import types

import pytest

from services.live_media.pyvirtualcam_adapter import PyVirtualCameraSink


class FakeCamera:
    def __init__(self, **kwargs):
        self.frames = []

    def send(self, frame):
        self.frames.append(frame)

    def sleep_until_next_frame(self):
        pass

    def close(self):
        pass


class Frame:
    shape = (256, 256, 3)
    dtype = "uint8"


class BadShape:
    shape = (128, 128, 3)
    dtype = "uint8"


class BadDtype:
    shape = (256, 256, 3)
    dtype = "float32"


def test_accepts_rgb_uint8_frame(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyvirtualcam", types.SimpleNamespace(Camera=FakeCamera))
    sink = PyVirtualCameraSink().open()
    asyncio.run(sink.send(Frame()))
    assert len(sink._camera.frames) == 1


@pytest.mark.parametrize("frame", [BadShape(), BadDtype()])
def test_rejects_invalid_frame_contract(monkeypatch, frame):
    monkeypatch.setitem(sys.modules, "pyvirtualcam", types.SimpleNamespace(Camera=FakeCamera))
    sink = PyVirtualCameraSink().open()
    with pytest.raises(ValueError):
        asyncio.run(sink.send(frame))
