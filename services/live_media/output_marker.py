"""Session-fixed synthetic-media label burned into outbound video pixels."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class MarkerPosition:
    """Position in the usable area, independent of frame resolution."""

    x: float = 1.0
    y: float = 0.0

    def __post_init__(self) -> None:
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
               for v in (self.x, self.y)):
            raise ValueError("marker coordinates must be finite numbers between zero and one")


def marker_bounds(width: int, height: int, position: MarkerPosition) -> tuple[int, int, int, int]:
    if width < 640 or height < 360:
        raise ValueError("outbound video is too small for the synthetic-media marker")
    margin = max(8, round(min(width, height) * 0.012))
    badge_width = min(round(width * 0.27), 360)
    badge_height = max(32, round(height * 0.052))
    left = margin + round(position.x * max(0, width - badge_width - margin * 2))
    top = margin + round(position.y * max(0, height - badge_height - margin * 2))
    return left, top, left + badge_width, top + badge_height


def burn_marker(image: Image.Image, position: MarkerPosition) -> Image.Image:
    """Return an RGB image with an opaque, visible label; never modify source media."""
    result = image.convert("RGB")
    bounds = marker_bounds(*result.size, position)
    draw = ImageDraw.Draw(result)
    draw.rounded_rectangle(bounds, radius=8, fill=(9, 18, 33), outline=(245, 249, 255), width=2)
    label = "AI-MODIFIED"
    size = max(16, min(30, round(result.height * 0.024)))
    font = ImageFont.load_default(size=size)
    box = draw.textbbox((0, 0), label, font=font)
    x = bounds[0] + (bounds[2] - bounds[0] - (box[2] - box[0])) // 2
    y = bounds[1] + (bounds[3] - bounds[1] - (box[3] - box[1])) // 2 - box[1]
    draw.text((x, y), label, fill=(255, 255, 255), font=font)
    return result
