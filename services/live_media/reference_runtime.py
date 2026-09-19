"""Runtime composition for reference-conditioned LiveShift Face v0.1."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .aiortc_video_track import attach_video_track
from .av_video_codec import decode_av_video_frame, encode_av_video_frame
from .inference_backend import FaceInferenceBackend
from .model_adapters import AuthorizedFaceAdapter
from .pipeline import LivePipeline
from .processors import MediaFrame, PassthroughAudioProcessor

ReferenceTensorProvider = Callable[[str], object]


class ReferenceTensorOnnxBackend(FaceInferenceBackend):
    """Run Face v0.1 directly on normalized source/reference tensors."""

    def __init__(
        self,
        session: object,
        *,
        reference_provider: ReferenceTensorProvider,
    ) -> None:
        self._session = session
        self._reference_provider = reference_provider

    def _transform(self, source: object, profile_id: str) -> object:
        if not profile_id:
            raise ValueError("authorized face profile is required")
        reference = self._reference_provider(profile_id)
        outputs = self._session.run(
            ["transformed_image"],
            {"source_image": source, "reference_image": reference},
        )
        if len(outputs) != 1:
            raise RuntimeError("Face v0.1 ONNX session returned an invalid output")
        return outputs[0]

    async def transform_video(
        self, frame: MediaFrame, profile_id: str
    ) -> MediaFrame:
        output = await asyncio.to_thread(
            self._transform, frame.payload, profile_id
        )
        return MediaFrame(payload=output, timestamp_ms=frame.timestamp_ms)


def build_reference_face_pipeline(
    session: object,
    *,
    face_profile_id: str,
    reference_provider: ReferenceTensorProvider,
) -> LivePipeline:
    """Compose the verified ONNX contract into the authorized LivePipeline."""
    if not face_profile_id:
        raise ValueError("authorized face profile is required")
    backend = ReferenceTensorOnnxBackend(
        session,
        reference_provider=reference_provider,
    )
    return LivePipeline(
        video=AuthorizedFaceAdapter(backend),
        audio=PassthroughAudioProcessor(),
        face_profile_id=face_profile_id,
    )


def attach_reference_face_track(
    peer: object,
    source_track: object,
    session: object,
    *,
    face_profile_id: str,
    reference_provider: ReferenceTensorProvider,
) -> object:
    """Compose ONNX inference, PyAV codecs, and the outbound peer track."""
    pipeline = build_reference_face_pipeline(
        session,
        face_profile_id=face_profile_id,
        reference_provider=reference_provider,
    )
    return attach_video_track(
        peer,
        source_track,
        pipeline,
        decode_frame=decode_av_video_frame,
        encode_frame=encode_av_video_frame,
    )
