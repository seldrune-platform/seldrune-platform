import asyncio

from services.live_media.processors import MediaFrame
from services.live_media.reference_runtime import (
    ReferenceTensorOnnxBackend,
    build_reference_face_pipeline,
)


class _Session:
    def __init__(self):
        self.feeds = None

    def run(self, outputs, feeds):
        assert outputs == ["transformed_image"]
        self.feeds = feeds
        return ["transformed-tensor"]


def test_tensor_backend_uses_reference_conditioned_contract():
    session = _Session()
    backend = ReferenceTensorOnnxBackend(
        session,
        reference_provider=lambda profile: f"reference:{profile}",
    )

    result = asyncio.run(
        backend.transform_video(
            MediaFrame(payload="source-tensor", timestamp_ms=77),
            "authorized-profile",
        )
    )

    assert session.feeds == {
        "source_image": "source-tensor",
        "reference_image": "reference:authorized-profile",
    }
    assert result.payload == "transformed-tensor"
    assert result.timestamp_ms == 77


def test_pipeline_composes_authorized_face_backend():
    session = _Session()
    pipeline = build_reference_face_pipeline(
        session,
        face_profile_id="authorized-profile",
        reference_provider=lambda profile: f"reference:{profile}",
    )

    result = asyncio.run(
        pipeline.video_frame(MediaFrame(payload="source-tensor", timestamp_ms=9))
    )

    assert result.payload == "transformed-tensor"
    assert session.feeds["reference_image"] == "reference:authorized-profile"
