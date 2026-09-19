"""aiortc peer-track bridge for the LiveShift video pipeline."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .pipeline import LivePipeline
from .processors import MediaFrame

DecodeVideoFrame = Callable[[object], Awaitable[MediaFrame]]
EncodeVideoFrame = Callable[[MediaFrame, object], Awaitable[object]]


class LiveShiftVideoTrack:
    """Provider-neutral transform wrapper used by unit tests and adapters."""

    kind = "video"

    def __init__(
        self,
        source_track: object,
        pipeline: LivePipeline,
        *,
        decode_frame: DecodeVideoFrame,
        encode_frame: EncodeVideoFrame,
    ) -> None:
        self._source_track = source_track
        self._pipeline = pipeline
        self._decode_frame = decode_frame
        self._encode_frame = encode_frame

    async def recv(self) -> object:
        source_av_frame = await self._source_track.recv()
        media_frame = await self._decode_frame(source_av_frame)
        transformed = await self._pipeline.video_frame(media_frame)
        return await self._encode_frame(transformed, source_av_frame)


def _build_real_aiortc_track(
    source_track: object,
    pipeline: LivePipeline,
    *,
    decode_frame: DecodeVideoFrame,
    encode_frame: EncodeVideoFrame,
) -> object:
    """Return a genuine aiortc MediaStreamTrack when aiortc is installed."""
    try:
        from aiortc import VideoStreamTrack
    except ImportError:
        return LiveShiftVideoTrack(
            source_track,
            pipeline,
            decode_frame=decode_frame,
            encode_frame=encode_frame,
        )

    class _AiortcLiveShiftVideoTrack(VideoStreamTrack):
        def __init__(self) -> None:
            super().__init__()

        async def recv(self) -> object:
            source_av_frame = await source_track.recv()
            media_frame = await decode_frame(source_av_frame)
            transformed = await pipeline.video_frame(media_frame)
            return await encode_frame(transformed, source_av_frame)

    return _AiortcLiveShiftVideoTrack()


def attach_video_track(
    peer: object,
    source_track: object,
    pipeline: LivePipeline,
    *,
    decode_frame: DecodeVideoFrame,
    encode_frame: EncodeVideoFrame,
) -> object:
    """Attach a transformed outbound video track to an aiortc peer."""
    track = _build_real_aiortc_track(
        source_track,
        pipeline,
        decode_frame=decode_frame,
        encode_frame=encode_frame,
    )
    peer.addTrack(track)
    return track
