import asyncio

import pytest

from services.live_media.pipeline import LivePipeline
from services.live_media.processors import MediaFrame, PassthroughVideoProcessor
from services.live_media.voice_runtime import AuthorizedVoiceProcessor


def test_authorized_voice_processor_preserves_timestamp():
    async def transform(payload, profile_id):
        assert profile_id == "consented-voice"
        return payload + b"-converted"

    pipeline = LivePipeline(
        video=PassthroughVideoProcessor(),
        audio=AuthorizedVoiceProcessor(transform),
        voice_profile_id="consented-voice",
    )
    result = asyncio.run(pipeline.audio_frame(MediaFrame(b"speech", 42)))
    assert result.payload == b"speech-converted"
    assert result.timestamp_ms == 42


def test_authorized_voice_processor_rejects_missing_profile():
    async def transform(payload, profile_id):
        return payload

    processor = AuthorizedVoiceProcessor(transform)
    with pytest.raises(ValueError, match="authorized voice profile"):
        asyncio.run(processor.process(MediaFrame(b"speech", 1), ""))
