import asyncio
import sys
import types

from services.live_media.pyvirtualcam_adapter import PyVirtualCameraSink
from services.live_media.virtual_camera_runtime_proof import prove_virtual_camera_delivery


class FakeCamera:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.frames = []
        self.closed = False

    def send(self, frame):
        self.frames.append(frame)

    def sleep_until_next_frame(self):
        pass

    def close(self):
        self.closed = True


def test_pyvirtualcam_sink_and_runtime_evidence(monkeypatch):
    module = types.SimpleNamespace(Camera=FakeCamera)
    monkeypatch.setitem(sys.modules, "pyvirtualcam", module)
    sink = PyVirtualCameraSink().open()
    frame = object()
    receipt = asyncio.run(prove_virtual_camera_delivery(sink, frame))
    assert receipt.state == "succeeded"
    assert receipt.virtual_camera_connected is True
    assert receipt.frames_delivered == 1
    sink.close()
    assert sink.connected is False


def test_sink_rejects_delivery_before_open():
    sink = PyVirtualCameraSink()
    try:
        asyncio.run(sink.send(object()))
    except RuntimeError as exc:
        assert "not open" in str(exc)
    else:
        raise AssertionError("expected unopened virtual camera to fail")
