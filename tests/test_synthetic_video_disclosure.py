"""Regression checks for mandatory LiveShell disclosure configuration."""

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


def test_worker_disclosure_stage_validates_without_duplicate_pixel_marker() -> None:
    source = Image.new("RGB", (640, 360), (12, 34, 56))
    buffer = io.BytesIO()
    source.save(buffer, format="JPEG", quality=90, optimize=False, subsampling=1)
    payload = buffer.getvalue()

    returned = asyncio.run(label_jpeg(payload))
    assert returned == payload


def test_worker_disclosure_stage_rejects_non_image_payload() -> None:
    with pytest.raises(ValueError, match="decodable image"):
        asyncio.run(label_jpeg(b"not-a-jpeg"))
