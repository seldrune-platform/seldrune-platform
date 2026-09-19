"""Tests for verified ONNX/CUDA Face backend adapters."""

import asyncio

import pytest

from services.live_media.face_onnx_backend import (
    AuthorizedReferenceProfile,
    LiveOnnxFaceInferenceBackend,
    OnnxFaceTransformBackend,
)
from services.live_media.face_onnx_loader import LoadedFaceModel
from services.live_media.processors import MediaFrame


class Codec:
    def encode(self, source_frame: bytes, reference_image: bytes):
        return {"source_image": source_frame, "reference_image": reference_image}

    def decode(self, transformed_tensor):
        return transformed_tensor


class Session:
    def run(self, output_names, tensors):
        assert output_names == ["transformed_image"]
        return [b"onnx-output:" + tensors["source_image"] + tensors["reference_image"]]


def _model(*, inputs=("source_image", "reference_image")) -> LoadedFaceModel:
    return LoadedFaceModel(
        path="/models/face.onnx",
        sha256="a" * 64,
        providers=("CUDAExecutionProvider",),
        input_names=inputs,
        output_names=("transformed_image",),
    )


def _profile() -> AuthorizedReferenceProfile:
    return AuthorizedReferenceProfile(
        profile_id="owner-profile",
        reference_image=b"authorized-reference",
        authorization_verified=True,
        synthetic_media_indicator_enabled=True,
    )


def test_onnx_backend_executes_reference_conditioned_contract() -> None:
    backend = OnnxFaceTransformBackend(Session(), _model(), Codec())
    output = backend.transform(b"source-frame", b"reference")
    assert output.startswith(b"onnx-output:")
    assert backend.model.providers[0] == "CUDAExecutionProvider"


def test_onnx_backend_rejects_embedding_only_model() -> None:
    with pytest.raises(ValueError, match="reference-conditioned"):
        OnnxFaceTransformBackend(
            Session(),
            _model(inputs=("image", "identity_embedding")),
            Codec(),
        )


def test_live_backend_preserves_timestamp_and_requires_profile() -> None:
    backend = LiveOnnxFaceInferenceBackend(
        OnnxFaceTransformBackend(Session(), _model(), Codec()),
        (_profile(),),
    )
    output = asyncio.run(backend.transform_video(MediaFrame(b"source", 123), "owner-profile"))
    assert output.payload != b"source"
    assert output.timestamp_ms == 123
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(backend.transform_video(MediaFrame(b"source", 123), "missing"))


def test_profile_requires_authorization_and_disclosure() -> None:
    with pytest.raises(ValueError, match="authorization"):
        AuthorizedReferenceProfile("profile", b"reference", False, True).validate()
    with pytest.raises(ValueError, match="indicator"):
        AuthorizedReferenceProfile("profile", b"reference", True, False).validate()
