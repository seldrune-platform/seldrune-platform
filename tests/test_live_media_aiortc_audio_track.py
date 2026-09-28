import asyncio

from services.live_media.aiortc_audio_track import LiveShiftAudioTrack
from services.live_media.processors import MediaFrame


class Source:
    async def recv(self):
        return object()


class Pipeline:
    async def audio_frame(self, frame):
        return frame


def test_audio_track_awaits_async_codec_functions():
    async def scenario():
        async def decode(_frame):
            return MediaFrame(b"pcm", 12, sample_rate_hz=48000, channels=1)

        async def encode(frame, _original):
            return {"payload": frame.payload, "sample_rate": 48000}

        track = LiveShiftAudioTrack(
            Source(),
            Pipeline(),
            decode_frame=decode,
            encode_frame=encode,
        )
        returned = await track.recv()
        assert returned == {"payload": b"pcm", "sample_rate": 48000}

    asyncio.run(scenario())
