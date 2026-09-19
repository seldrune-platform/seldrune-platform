import asyncio

from services.live_media.virtual_camera import VirtualCameraBridge


class Sink:
    def __init__(self):
        self.frames = []

    async def send(self, frame):
        self.frames.append(frame)


def test_virtual_camera_bridge_records_real_delivery():
    sink = Sink()
    bridge = VirtualCameraBridge(sink)
    evidence = asyncio.run(bridge.deliver({"rgb": b"frame"}))
    assert sink.frames == [{"rgb": b"frame"}]
    assert evidence.frames_delivered == 1
    assert evidence.sink_connected is True
    assert evidence.verified is True
