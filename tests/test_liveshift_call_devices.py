import asyncio
import sys
import types

import pytest

from clients.desktop.liveshift_call_devices import (
    DesktopLiveCallOutput, SoundDeviceVirtualMicrophoneSink, relay_returned_track,
)


class Camera:
    connected = True
    def __init__(self): self.frames = []
    def open(self): return self
    async def send(self, frame): self.frames.append(frame)
    def close(self): pass


class Microphone:
    connected = True
    def __init__(self): self.chunks = []
    def open(self): return self
    async def send(self, chunk): self.chunks.append(chunk)
    async def close(self): pass


def build(**overrides):
    camera, microphone = Camera(), Microphone()
    args = dict(
        camera_sink=camera, microphone_sink=microphone,
        face_profile_id="owner-face", voice_profile_id="owner-voice",
        authorization_check=lambda face, voice: face == "owner-face" and voice == "owner-voice",
        width=320, height=240,
    )
    args.update(overrides)
    return DesktopLiveCallOutput(**args), camera, microphone


def test_authorization_and_disclosure_fail_closed():
    output, _, _ = build(authorization_check=lambda *_: False)
    with pytest.raises(PermissionError): output.start()
    output, _, _ = build(disclosure_enabled=False)
    with pytest.raises(ValueError, match="disclosure"): output.start()


def test_publishes_badged_video_audio_and_receipt():
    output, camera, microphone = build()
    output.start()
    frame = bytes(320 * 240 * 3)
    asyncio.run(output.publish_video(frame, 33))
    asyncio.run(output.publish_audio(b"\0\0" * 480, 10))
    assert camera.frames[0].shape == (240, 320, 3)
    assert camera.frames[0].dtype.name == "uint8"
    assert camera.frames[0].any()
    assert microphone.chunks == [b"\0\0" * 480]
    assert output.receipt.verified
    assert output.receipt.as_dict()["desktop_call_output_verified"]


def test_rejects_invalid_video_and_nonmonotonic_timestamps():
    output, _, _ = build()
    output.start()
    with pytest.raises(ValueError, match="RGB24"):
        asyncio.run(output.publish_video(b"bad", 1))
    frame = bytes(320 * 240 * 3)
    asyncio.run(output.publish_video(frame, 33))
    with pytest.raises(ValueError, match="monotonic"):
        asyncio.run(output.publish_video(frame, 32))


class FakeStream:
    def __init__(self, **kwargs): self.kwargs, self.writes = kwargs, []
    def start(self): pass
    def write(self, chunk): self.writes.append(chunk)
    def stop(self): pass
    def close(self): self.closed = True


def test_audio_sink_selects_exact_virtual_device(monkeypatch):
    streams = []
    devices = [
        {"name": "Speakers", "max_output_channels": 2},
        {"name": "Cable Input", "max_output_channels": 2},
    ]
    monkeypatch.setitem(
        sys.modules, "sounddevice",
        types.SimpleNamespace(query_devices=lambda: devices,
                              RawOutputStream=lambda **kwargs: streams.append(FakeStream(**kwargs)) or streams[-1]),
    )
    sink = SoundDeviceVirtualMicrophoneSink("Cable Input")
    sink.open()
    asyncio.run(sink.send(b"\0\0" * 480))
    asyncio.run(sink.close())
    stream = streams[0]
    assert stream.kwargs["device"] == 1
    assert stream.writes == [b"\0\0" * 480]



class Frame:
    def __init__(self, array, *, sample_rate=None, channels=1):
        self.array = array
        self.sample_rate = sample_rate
        self.layout = types.SimpleNamespace(channels=[object()] * channels)
        self.pts, self.time_base = 480, 1 / 48_000

    def to_ndarray(self, format):
        return self.array


class Track:
    kind = "video"
    def __init__(self, frames): self.frames = iter(frames)
    async def recv(self):
        try: return next(self.frames)
        except StopIteration: raise StopAsyncIteration


def test_relay_returned_webrtc_video_track():
    import numpy as np
    output, camera, _ = build(width=320, height=240)
    output.start()
    frame = Frame(np.zeros((240, 320, 3), dtype=np.uint8))
    asyncio.run(relay_returned_track(Track([frame]), output))
    assert len(camera.frames) == 1
    assert camera.frames[0].shape == (240, 320, 3)
    assert output.receipt.video_frames == 1
