"""aiortc audio-track wrapper for LiveShift voice conversion."""

from __future__ import annotations

from collections.abc import Callable

from .pipeline import LivePipeline
from .processors import MediaFrame
from .transport_metadata import DeliveredAudioMetadata

DecodeAudioFrame = Callable[[object], MediaFrame]
EncodeAudioFrame = Callable[[MediaFrame, object], object]


class LiveShiftAudioTrack:
    kind = "audio"

    def __init__(
        self,
        source_track: object,
        pipeline: LivePipeline,
        *,
        decode_frame: DecodeAudioFrame,
        encode_frame: EncodeAudioFrame,
        metadata_observer: object | None = None,
    ) -> None:
        self._source_track = source_track
        self._pipeline = pipeline
        self._decode_frame = decode_frame
        self._encode_frame = encode_frame
        self._metadata_observer = metadata_observer

    async def recv(self) -> object:
        source = await self._source_track.recv()
        decoded = self._decode_frame(source)
        transformed = await self._pipeline.audio_frame(decoded)
        returned = self._encode_frame(transformed, source)
        if self._metadata_observer is not None:
            sample_rate = getattr(returned, "sample_rate", None)
            if sample_rate is not None:
                self._metadata_observer.record_delivered_audio_metadata(
                    DeliveredAudioMetadata(int(sample_rate))
                )
        return returned


def _build_real_aiortc_audio_track(
    source_track: object,
    pipeline: LivePipeline,
    *,
    decode_frame: DecodeAudioFrame,
    encode_frame: EncodeAudioFrame,
) -> object:
    try:
        from aiortc import MediaStreamTrack
    except ImportError:
        return LiveShiftAudioTrack(
            source_track,
            pipeline,
            decode_frame=decode_frame,
            encode_frame=encode_frame,
        )

    class _AiortcLiveShiftAudioTrack(MediaStreamTrack):
        kind = "audio"

        def __init__(self) -> None:
            super().__init__()

        async def recv(self) -> object:
            source = await source_track.recv()
            decoded = decode_frame(source)
            transformed = await pipeline.audio_frame(decoded)
            return encode_frame(transformed, source)

    return _AiortcLiveShiftAudioTrack()


def attach_audio_track(
    peer: object,
    source_track: object,
    pipeline: LivePipeline,
    *,
    decode_frame: DecodeAudioFrame,
    encode_frame: EncodeAudioFrame,
) -> object:
    track = _build_real_aiortc_audio_track(
        source_track,
        pipeline,
        decode_frame=decode_frame,
        encode_frame=encode_frame,
    )
    peer.addTrack(track)
    return track
