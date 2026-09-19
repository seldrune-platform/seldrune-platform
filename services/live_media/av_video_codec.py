"""PyAV/NumPy codecs for LiveShift Face v0.1 video frames.

Heavy realtime-media dependencies are imported lazily so the core API can run
without the optional GPU/WebRTC stack.
"""

from __future__ import annotations

import asyncio

from .processors import MediaFrame


def _imports():
    try:
        import numpy as np
        from av import VideoFrame
    except ImportError as exc:
        raise RuntimeError(
            "PyAV and NumPy are required for LiveShift video frame codecs"
        ) from exc
    return np, VideoFrame


async def decode_av_video_frame(frame: object) -> MediaFrame:
    """Convert a PyAV VideoFrame to normalized NCHW float32 Face v0.1 input."""
    np, _ = _imports()

    def convert():
        rgb = frame.to_ndarray(format="rgb24")
        resized = _resize_rgb(rgb, 256, 256)
        tensor = resized.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
        timestamp_ms = 0
        if getattr(frame, "time", None) is not None:
            timestamp_ms = int(float(frame.time) * 1000)
        return MediaFrame(payload=tensor, timestamp_ms=timestamp_ms)

    return await asyncio.to_thread(convert)


async def encode_av_video_frame(frame: MediaFrame, original: object) -> object:
    """Convert Face v0.1 NCHW output into a PyAV VideoFrame."""
    np, VideoFrame = _imports()

    def convert():
        tensor = np.asarray(frame.payload)
        if tensor.shape == (1, 3, 256, 256):
            tensor = tensor[0]
        if tensor.shape != (3, 256, 256):
            raise ValueError("Face v0.1 output must have shape (1,3,256,256)")
        rgb = np.transpose(tensor, (1, 2, 0))
        rgb = (np.clip(rgb, 0.0, 1.0) * 255.0).round().astype(np.uint8)
        output = VideoFrame.from_ndarray(rgb, format="rgb24")
        output.pts = getattr(original, "pts", None)
        output.time_base = getattr(original, "time_base", None)
        return output

    return await asyncio.to_thread(convert)


def _resize_rgb(image: object, width: int, height: int) -> object:
    """Resize RGB ndarray using Pillow, imported only by realtime workers."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for LiveShift frame resize") from exc
    image_cls = Image
    resized = image_cls.fromarray(image).resize((width, height))
    import numpy as np

    return np.asarray(resized)
