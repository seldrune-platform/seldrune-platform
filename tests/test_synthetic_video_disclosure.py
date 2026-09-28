"""Regression checks for mandatory, readable LiveShell disclosure."""

from __future__ import annotations

import asyncio
import io

import pytest
from PIL import Image

from services.live_media.synthetic_disclosure import (
    SUPPORTED_DISCLOSURE_LABELS,
    validate_disclosure_label,
)
from services.live_media.synthetic_video_labeler import label_jpeg


@pytest.mark.parametrize("label", sorted(SUPPORTED_DISCLOSURE_LABELS))
def test_supported_labels_are_explicit(label: str) -> None:
    assert validate_disclosure_label(label) == label


@pytest.mark.parametrize(
    "label",
    ["", "   ", "Seldrune Live", "FILTER ON", None],
)
def test_blank_or_ambiguous_labels_fail_closed(label: str) -> None:
    with pytest.raises(ValueError, match="approved visible disclosure"):
        validate_disclosure_label(label)


def test_every_labeled_frame_contains_high_contrast_disclosure() -> None:
    source = Image.new("RGB", (640, 360), (0, 0, 0))
    buffer = io.BytesIO()
    source.save(buffer, format="JPEG")
    payload = buffer.getvalue()

    for _ in range(2):
        labeled = asyncio.run(label_jpeg(payload))
        with Image.open(io.BytesIO(labeled)) as output:
            region = output.convert("RGB").crop((0, 0, 300, 80))
            pixels = region.load()
            assert any(
                pixels[x, y][0] > 200
                and pixels[x, y][1] > 200
                and pixels[x, y][2] > 200
                for y in range(region.height)
                for x in range(region.width)
            )
