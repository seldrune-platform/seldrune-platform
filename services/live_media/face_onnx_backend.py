"""ONNX/CUDA backend adapters for authorized Seldrune Face transforms."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from services.live_media.face_onnx_loader import LoadedFaceModel
from services.live_media.inference_backend import FaceInferenceBackend
from services.live_media.processors import MediaFrame


class FaceTensorCodec(Protocol):
    def encode(self, source_frame: bytes, reference_image: bytes) -> dict[str, Any]: ...

    def decode(self, transformed_tensor: Any) -> bytes: ...


@dataclass(frozen=True)
class AuthorizedReferenceProfile:
    profile_id: str
    reference_image: bytes
    authorization_verified: bool
    synthetic_media_indicator_enabled: bool

    def validate(self) -> None:
        if not self.profile_id.strip() or not self.reference_image:
            raise ValueError("authorized reference profile is incomplete")
        if not self.authorization_verified:
            raise ValueError("reference profile authorization is required")
        if not self.synthetic_media_indicator_enabled:
            raise ValueError("synthetic-media indicator must be enabled")


class OnnxFaceTransformBackend:
    """Synchronous transform backend for a verified reference-conditioned ONNX session."""

    def __init__(self, session: Any, model: LoadedFaceModel, codec: FaceTensorCodec) -> None:
        required = {"source_image", "reference_image"}
        if not required.issubset(model.input_names):
            raise ValueError("ONNX backend requires a reference-conditioned model")
        if "transformed_image" not in model.output_names:
            raise ValueError("ONNX backend requires transformed_image output")
        self._session = session
        self._model = model
        self._codec = codec

    @property
    def model(self) -> LoadedFaceModel:
        return self._model

    def transform(self, source_frame: bytes, reference_image: bytes) -> bytes:
        if not source_frame or not reference_image:
            raise ValueError("source and reference image bytes are required")
        tensors = self._codec.encode(source_frame, reference_image)
        if set(tensors) != {"source_image", "reference_image"}:
            raise ValueError("tensor codec returned an invalid Face input contract")
        outputs = self._session.run(["transformed_image"], tensors)
        if len(outputs) != 1:
            raise ValueError("ONNX session returned an invalid Face output contract")
        transformed = self._codec.decode(outputs[0])
        if not transformed:
            raise ValueError("ONNX Face transform returned an empty frame")
        return transformed


class LiveOnnxFaceInferenceBackend(FaceInferenceBackend):
    """Async LiveShift adapter backed by verified ONNX/CUDA inference."""

    def __init__(
        self,
        backend: OnnxFaceTransformBackend,
        profiles: tuple[AuthorizedReferenceProfile, ...],
    ) -> None:
        self._backend = backend
        self._profiles = {}
        for profile in profiles:
            profile.validate()
            if profile.profile_id in self._profiles:
                raise ValueError("authorized profile identifiers must be unique")
            self._profiles[profile.profile_id] = profile

    async def transform_video(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise ValueError("authorized reference profile was not found")
        transformed = await asyncio.to_thread(
            self._backend.transform,
            frame.payload,
            profile.reference_image,
        )
        if transformed == frame.payload:
            raise ValueError("ONNX Face backend returned an unchanged frame")
        return MediaFrame(transformed, frame.timestamp_ms)
