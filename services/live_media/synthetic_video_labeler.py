"""Fail-closed worker-stage validation before the gateway renders disclosure."""

from __future__ import annotations

import asyncio
import io

from PIL import Image, UnidentifiedImageError

from services.live_media.synthetic_disclosure import get_visible_disclosure_label

# Validate disclosure configuration during worker import/startup. The participant-visible
# marker itself is rendered exactly once at the WebRTC gateway's final video boundary.
get_visible_disclosure_label()


def _validate_jpeg_sync(payload: bytes) -> bytes:
    if not payload:
        raise ValueError("synthetic disclosure requires a video frame")
    try:
        with Image.open(io.BytesIO(payload)) as source:
            source.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("synthetic disclosure requires a decodable image") from exc
    return payload


async def label_jpeg(payload: bytes) -> bytes:
    """Validate the transformed JPEG without adding a duplicate visible marker."""
    return await asyncio.to_thread(_validate_jpeg_sync, payload)
