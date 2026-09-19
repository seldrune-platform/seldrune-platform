import asyncio

import pytest

from services.live_media.combined_av_runtime import build_reference_av_pipeline


class FakeSession:
    def run(self, outputs, inputs):
        return [inputs["source_image"]]


def test_combined_av_pipeline_shares_sync_state():
    async def voice_inference(speech, reference):
        return speech

    pipeline = build_reference_av_pipeline(
        FakeSession(),
        face_profile_id="face-owner",
        face_reference_provider=lambda profile_id: object(),
        voice_profile_id="voice-owner",
        voice_reference_provider=lambda profile_id: b"voice-reference",
        voice_inference=voice_inference,
    )
    assert pipeline.face_profile_id == "face-owner"
    assert pipeline.voice_profile_id == "voice-owner"
    assert pipeline.sync is not None
    assert pipeline.sync.correction() == "none"


def test_combined_av_pipeline_requires_both_authorizations():
    async def voice_inference(speech, reference):
        return speech

    with pytest.raises(ValueError, match="authorized face and voice profiles"):
        build_reference_av_pipeline(
            FakeSession(),
            face_profile_id="face-owner",
            face_reference_provider=lambda profile_id: object(),
            voice_profile_id="",
            voice_reference_provider=lambda profile_id: b"voice-reference",
            voice_inference=voice_inference,
        )
