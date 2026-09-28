"""Persistent visible disclosure for LiveShell synthetic video frames."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

from services.live_media.synthetic_disclosure import get_visible_disclosure_label

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

_LABEL = get_visible_disclosure_label()
_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def _font(height: int) -> ImageFont.ImageFont:
    size = max(18, min(42, height // 28))
    for path in _FONT_CANDIDATES:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _label_jpeg_sync(payload: bytes) -> bytes:
    if not payload:
        raise ValueError("synthetic disclosure requires a video frame")
    try:
        with Image.open(io.BytesIO(payload)) as source:
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("synthetic disclosure requires a decodable image") from exc

    width, height = image.size
    if width < 1 or height < 1:
        raise ValueError("synthetic disclosure received invalid image dimensions")

    draw = ImageDraw.Draw(image)
    font = _font(height)
    margin = max(10, min(width, height) // 80)
    stroke = max(1, height // 720)
    box = draw.textbbox((0, 0), _LABEL, font=font, stroke_width=stroke)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    pad_x = max(8, text_height // 2)
    pad_y = max(6, text_height // 3)
    rect = (
        margin,
        margin,
        min(width - margin, margin + text_width + 2 * pad_x),
        min(height - margin, margin + text_height + 2 * pad_y),
    )
    draw.rounded_rectangle(rect, radius=max(4, text_height // 4), fill=(0, 0, 0))
    draw.text(
        (margin + pad_x, margin + pad_y),
        _LABEL,
        fill=(255, 255, 255),
        font=font,
        stroke_width=stroke,
        stroke_fill=(0, 0, 0),
    )

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90, optimize=False, subsampling=1)
    result = output.getvalue()
    if not result:
        raise RuntimeError("synthetic disclosure produced no output")
    return result


async def label_jpeg(payload: bytes) -> bytes:
    """Burn a readable disclosure into every outbound live video frame."""
    return await asyncio.to_thread(_label_jpeg_sync, payload)
