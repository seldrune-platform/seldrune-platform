import asyncio

from services.live_media.processors import MediaFrame
from services.liveshell.hd_voice_runtime import LiveShellHDVoiceProcessor


def test_hd_voice_preserves_timestamp_and_routes_reference():
    async def transform(payload, reference):
        assert reference == "voice-reference"
        return payload

    processor = LiveShellHDVoiceProcessor(
        transform=transform,
        reference_provider=lambda profile: (
            "voice-reference" if profile == "voice-1" else None
        ),
    )
    frame = MediaFrame(payload=b"audio", timestamp_ms=120)
    result = asyncio.run(processor.process(frame, "voice-1"))
    assert result.payload == b"audio"
    assert result.timestamp_ms == 120
    assert processor.sample_rate == 48000
