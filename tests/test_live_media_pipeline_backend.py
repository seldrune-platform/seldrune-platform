"""Tests for the LiveShift pipeline-backed face inference adapter."""

import asyncio

from services.live_media.pipeline_backend import PipelineFaceInferenceBackend
from services.live_media.processors import MediaFrame


def test_pipeline_backend_returns_frame_and_records_metrics():
    async def transform(payload: bytes, profile_id: str) -> bytes:
        assert payload == b"prepared-source"
        assert profile_id == "authorized-profile"
        return b"gpu-result"

    backend = PipelineFaceInferenceBackend(
        transform,
        preprocess=lambda payload: b"prepared-" + payload,
        composite=lambda source, transformed: source + b"|" + transformed,
    )

    output = asyncio.run(
        backend.transform_video(
            MediaFrame(payload=b"source", timestamp_ms=9876),
            "authorized-profile",
        )
    )

    assert output.payload == b"source|gpu-result"
    assert output.timestamp_ms == 9876
    assert backend.last_metrics is not None
    assert backend.last_metrics.preprocess_ms >= 0
    assert backend.last_metrics.inference_ms >= 0
    assert backend.last_metrics.composite_ms >= 0
    assert backend.last_metrics.total_ms >= 0


def test_pipeline_backend_can_be_used_for_first_frame_milestone():
    async def transform(payload: bytes, profile_id: str) -> bytes:
        return b"transformed"

    backend = PipelineFaceInferenceBackend(transform)
    output = asyncio.run(
        backend.transform_video(MediaFrame(b"source", 42), "profile")
    )

    assert output == MediaFrame(b"transformed", 42)
