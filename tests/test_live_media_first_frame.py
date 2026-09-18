import asyncio

import pytest

from services.live_media.first_frame import transform_first_frame
from services.live_media.inference_backend import FaceInferenceBackend
from services.live_media.milestones import ProductMilestones
from services.live_media.processors import MediaFrame


class FakeFaceBackend(FaceInferenceBackend):
    async def transform_video(
        self, frame: MediaFrame, profile_id: str
    ) -> MediaFrame:
        return MediaFrame(b"transformed:" + frame.payload, frame.timestamp_ms)


def test_first_frame_reports_real_change():
    result = asyncio.run(
        transform_first_frame(FakeFaceBackend(), b"frame", "face-1", 10)
    )
    assert result.transformed
    assert result.frame.payload == b"transformed:frame"


def test_first_frame_requires_profile():
    with pytest.raises(ValueError):
        asyncio.run(transform_first_frame(FakeFaceBackend(), b"frame", "", 10))


def test_product_milestones_do_not_overclaim():
    architecture_only = ProductMilestones()
    assert not architecture_only.first_visible_output_ready
    assert not architecture_only.meeting_call_ready

    visible = ProductMilestones(True, True, True, True)
    assert visible.first_visible_output_ready
    assert not visible.meeting_call_ready
