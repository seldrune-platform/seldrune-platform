from services.live_media.processors import MediaFrame
from services.live_media.reference_onnx_backend import ReferenceOnnxFaceBackend


class _Session:
    def __init__(self):
        self.calls = []

    def run(self, outputs, feeds):
        self.calls.append((outputs, feeds))
        return [b"onnx-output"]


def test_reference_backend_runs_source_reference_contract():
    session = _Session()
    backend = ReferenceOnnxFaceBackend(
        session,
        reference_provider=lambda profile_id: b"reference:" + profile_id.encode(),
        decode_image=lambda payload: b"decoded:" + payload,
        encode_image=lambda output: b"encoded:" + output,
    )

    import asyncio

    frame = asyncio.run(
        backend.transform_video(MediaFrame(b"source", 1234), "authorized-profile")
    )

    assert frame.payload == b"encoded:onnx-output"
    assert frame.timestamp_ms == 1234
    outputs, feeds = session.calls[0]
    assert outputs == ["transformed_image"]
    assert feeds == {
        "source_image": b"decoded:source",
        "reference_image": b"reference:authorized-profile",
    }


def test_reference_backend_rejects_empty_profile():
    backend = ReferenceOnnxFaceBackend(
        _Session(),
        reference_provider=lambda profile_id: b"reference",
        decode_image=lambda payload: payload,
        encode_image=lambda output: output,
    )

    import asyncio
    import pytest

    with pytest.raises(ValueError, match="authorized face profile"):
        asyncio.run(backend.transform_video(MediaFrame(b"source", 1), ""))
