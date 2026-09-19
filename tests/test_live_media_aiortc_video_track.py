import asyncio

from services.live_media.aiortc_video_track import (
    LiveShiftVideoTrack,
    attach_video_track,
)
from services.live_media.pipeline import LivePipeline
from services.live_media.processors import (
    MediaFrame,
    PassthroughAudioProcessor,
    VideoProcessor,
)


class _SourceTrack:
    async def recv(self):
        return {"pixels": b"source", "pts": 42}


class _Transform(VideoProcessor):
    async def process(self, frame, profile_id):
        assert profile_id == "authorized-profile"
        return MediaFrame(frame.payload + b":face-v01", frame.timestamp_ms)


class _Peer:
    def __init__(self):
        self.tracks = []

    def addTrack(self, track):
        self.tracks.append(track)


async def _decode(frame):
    return MediaFrame(frame["pixels"], frame["pts"])


async def _encode(frame, original):
    return {
        "pixels": frame.payload,
        "pts": original["pts"],
    }


def _pipeline():
    return LivePipeline(
        video=_Transform(),
        audio=PassthroughAudioProcessor(),
        face_profile_id="authorized-profile",
    )


def test_peer_video_track_returns_transformed_frame():
    track = LiveShiftVideoTrack(
        _SourceTrack(),
        _pipeline(),
        decode_frame=_decode,
        encode_frame=_encode,
    )

    output = asyncio.run(track.recv())

    assert output["pixels"] == b"source:face-v01"
    assert output["pts"] == 42


def test_attach_video_track_registers_outbound_track():
    peer = _Peer()

    track = attach_video_track(
        peer,
        _SourceTrack(),
        _pipeline(),
        decode_frame=_decode,
        encode_frame=_encode,
    )

    assert peer.tracks == [track]
    assert track.kind == "video"
