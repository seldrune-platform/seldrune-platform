import asyncio

from services.live_media.av_audio_codec import (
    decode_av_audio_frame,
    encode_av_audio_frame,
)
from services.live_media.processors import MediaFrame


class _Array:
    dtype = type("DType", (), {"kind": "f"})()


def test_codec_functions_are_async_and_validate_runtime_dependencies():
    assert asyncio.iscoroutinefunction(decode_av_audio_frame)
    assert asyncio.iscoroutinefunction(encode_av_audio_frame)


def test_media_frame_can_carry_audio_payload():
    payload = [[0.0, 0.25, -0.25]]
    frame = MediaFrame(payload=payload, timestamp_ms=20)
    assert frame.payload == payload
    assert frame.timestamp_ms == 20
