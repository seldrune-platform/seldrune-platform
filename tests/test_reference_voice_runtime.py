import asyncio

import pytest

from services.live_media.processors import MediaFrame, PassthroughVideoProcessor
from services.live_media.reference_voice_runtime import (
    ReferenceVoiceProcessor,
    build_face_voice_pipeline,
)


def test_reference_voice_processor_uses_enrolled_reference():
    seen = {}

    def reference_provider(profile_id):
        assert profile_id == "voice-owner"
        return b"reference"

    async def inference(speech, reference):
        seen["speech"] = speech
        seen["reference"] = reference
        return b"converted"

    processor = ReferenceVoiceProcessor(
        reference_provider=reference_provider,
        inference=inference,
    )
    result = asyncio.run(
        processor.process(MediaFrame(payload=b"speech", timestamp_ms=120), "voice-owner")
    )
    assert result.payload == b"converted"
    assert result.timestamp_ms == 120
    assert seen == {"speech": b"speech", "reference": b"reference"}


def test_reference_voice_processor_requires_enrollment():
    async def inference(speech, reference):
        return speech

    processor = ReferenceVoiceProcessor(
        reference_provider=lambda profile_id: None,
        inference=inference,
    )
    with pytest.raises(ValueError, match="enrolled voice reference"):
        asyncio.run(processor.process(MediaFrame(b"speech", 1), "voice-owner"))


def test_combined_pipeline_requires_face_and_voice_profiles():
    async def inference(speech, reference):
        return speech

    pipeline = build_face_voice_pipeline(
        video=PassthroughVideoProcessor(),
        face_profile_id="face-owner",
        voice_profile_id="voice-owner",
        voice_reference_provider=lambda profile_id: b"reference",
        voice_inference=inference,
    )
    assert pipeline.face_profile_id == "face-owner"
    assert pipeline.voice_profile_id == "voice-owner"

    with pytest.raises(ValueError, match="authorized voice profile"):
        build_face_voice_pipeline(
            video=PassthroughVideoProcessor(),
            face_profile_id="face-owner",
            voice_profile_id="",
            voice_reference_provider=lambda profile_id: b"reference",
            voice_inference=inference,
        )
