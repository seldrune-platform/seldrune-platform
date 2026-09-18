"""Tests for the model-neutral authorized video inference pipeline."""

import asyncio

import pytest

from services.live_media.processors import MediaFrame
from services.live_media.video_inference_pipeline import VideoInferencePipeline


def test_pipeline_runs_preprocess_transform_composite_and_preserves_timestamp():
    calls = {}

    def preprocess(payload: bytes) -> bytes:
        calls["preprocess"] = payload
        return b"prepared-" + payload

    async def transform(payload: bytes, profile_id: str) -> bytes:
        calls["transform"] = (payload, profile_id)
        return b"model-output"

    def composite(source: bytes, transformed: bytes) -> bytes:
        calls["composite"] = (source, transformed)
        return b"composited"

    result = asyncio.run(
        VideoInferencePipeline(
            transform,
            preprocess=preprocess,
            composite=composite,
        ).run(MediaFrame(b"source", 1234), "authorized-profile")
    )

    assert calls["preprocess"] == b"source"
    assert calls["transform"] == (b"prepared-source", "authorized-profile")
    assert calls["composite"] == (b"source", b"model-output")
    assert result.frame.payload == b"composited"
    assert result.frame.timestamp_ms == 1234
    assert result.transformed is True
    assert result.metrics.preprocess_ms >= 0
    assert result.metrics.inference_ms >= 0
    assert result.metrics.composite_ms >= 0
    assert result.metrics.total_ms >= 0


def test_pipeline_reports_unchanged_output():
    async def transform(payload: bytes, profile_id: str) -> bytes:
        return payload

    result = asyncio.run(
        VideoInferencePipeline(transform).run(MediaFrame(b"same", 1), "profile")
    )

    assert result.transformed is False


@pytest.mark.parametrize(
    ("frame", "profile_id", "message"),
    [
        (MediaFrame(b"", 1), "profile", "video frame payload is required"),
        (MediaFrame(b"frame", 1), "", "authorized face profile is required"),
    ],
)
def test_pipeline_rejects_invalid_input(frame, profile_id, message):
    async def transform(payload: bytes, requested_profile: str) -> bytes:
        return payload

    with pytest.raises(ValueError, match=message):
        asyncio.run(VideoInferencePipeline(transform).run(frame, profile_id))


def test_pipeline_rejects_empty_backend_output():
    async def transform(payload: bytes, profile_id: str) -> bytes:
        return b""

    with pytest.raises(ValueError, match="face backend returned an empty frame"):
        asyncio.run(
            VideoInferencePipeline(transform).run(MediaFrame(b"source", 1), "profile")
        )
