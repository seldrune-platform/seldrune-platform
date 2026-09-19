import argparse
import asyncio
import sys
import types

from services.live_media import virtual_camera_device_proof as proof


class FakeCamera:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.frames = []

    def send(self, frame):
        self.frames.append(frame)

    def sleep_until_next_frame(self):
        pass

    def close(self):
        pass


class FakeArray:
    def __init__(self):
        self.shape = (16, 16, 3)


def test_real_device_proof_contract_with_fake_backend(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pyvirtualcam", types.SimpleNamespace(Camera=FakeCamera))
    monkeypatch.setattr(proof, "_load_rgb", lambda path, width, height: FakeArray())
    args = argparse.Namespace(
        frame=tmp_path / "frame.png",
        receipt=tmp_path / "receipt.json",
        width=16,
        height=16,
        fps=30,
        frames=3,
    )
    receipt = asyncio.run(proof._run(args))
    assert receipt["state"] == "succeeded"
    assert receipt["virtual_camera_connected"] is True
    assert receipt["frames_delivered"] == 3
