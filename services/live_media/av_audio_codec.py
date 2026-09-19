"""PyAV/NumPy codecs for LiveShift real-time audio frames."""

from __future__ import annotations

import asyncio

from .processors import MediaFrame


def _imports():
    try:
        import numpy as np
        from av import AudioFrame
    except ImportError as exc:
        raise RuntimeError(
            "PyAV and NumPy are required for LiveShift audio frame codecs"
        ) from exc
    return np, AudioFrame


async def decode_av_audio_frame(frame: object) -> MediaFrame:
    """Convert a PyAV AudioFrame to planar float32 audio for voice inference."""
    np, _ = _imports()

    def convert():
        samples = frame.to_ndarray()
        tensor = np.asarray(samples, dtype=np.float32)
        if tensor.dtype.kind in {"i", "u"}:
            tensor = tensor / max(float(np.iinfo(samples.dtype).max), 1.0)
        timestamp_ms = 0
        if getattr(frame, "time", None) is not None:
            timestamp_ms = int(float(frame.time) * 1000)
        return MediaFrame(payload=tensor, timestamp_ms=timestamp_ms)

    return await asyncio.to_thread(convert)


async def encode_av_audio_frame(frame: MediaFrame, original: object) -> object:
    """Convert processed audio to a PyAV frame while preserving RTP timing."""
    np, AudioFrame = _imports()

    def convert():
        samples = np.asarray(frame.payload, dtype=np.float32)
        if samples.ndim == 1:
            samples = samples[None, :]
        if samples.ndim != 2:
            raise ValueError("voice output must be mono/stereo planar audio")
        samples = np.clip(samples, -1.0, 1.0)
        output = AudioFrame.from_ndarray(samples, format="fltp")
        output.sample_rate = getattr(original, "sample_rate", 48000)
        output.pts = getattr(original, "pts", None)
        output.time_base = getattr(original, "time_base", None)
        return output

    return await asyncio.to_thread(convert)
