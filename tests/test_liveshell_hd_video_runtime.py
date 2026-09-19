import asyncio

import pytest

from services.live_media.interfaces import MediaFrame
from services.liveshell.hd_video_runtime import LiveShellHDVideoProcessor


class Frame:
    def __init__(self, shape):
        self.shape = shape


def test_hd_processor_preserves_resolution_and_timestamp():
    async def transform(payload, reference):
        assert reference == "authorized-reference"
        return Frame(payload.shape)

    processor = LiveShellHDVideoProcessor(
        transform=transform,
        reference_provider=lambda profile: (
            "authorized-reference" if profile == "face-1" else None
        ),
    )
    source = MediaFrame(Frame((720, 1280, 3)), timestamp_ms=42)
    result = asyncio.run(processor.process(source, "face-1"))
    assert result.payload.shape == (720, 1280, 3)
    assert result.timestamp_ms == 42


def test_hd_processor_rejects_sub_hd_frames():
    async def transform(payload, reference):
        return payload

    processor = LiveShellHDVideoProcessor(
        transform=transform,
        reference_provider=lambda profile: object(),
    )
    with pytest.raises(ValueError, match="1280x720"):
        asyncio.run(
            processor.process(
                MediaFrame(Frame((256, 256, 3)), timestamp_ms=0),
                "face-1",
            )
        )


def test_hd_processor_requires_enrolled_reference():
    async def transform(payload, reference):
        return payload

    processor = LiveShellHDVideoProcessor(
        transform=transform,
        reference_provider=lambda profile: None,
    )
    with pytest.raises(ValueError, match="enrolled"):
        asyncio.run(
            processor.process(
                MediaFrame(Frame((720, 1280, 3)), timestamp_ms=0),
                "face-1",
            )
        )
