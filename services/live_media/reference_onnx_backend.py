"""Reference-conditioned ONNX backend for authorized LiveShift face transforms."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .inference_backend import FaceInferenceBackend
from .processors import MediaFrame

DecodeImage = Callable[[bytes], object]
EncodeImage = Callable[[object], bytes]
ReferenceProvider = Callable[[str], object]


class ReferenceOnnxFaceBackend(FaceInferenceBackend):
    """Run source/reference Face v0.1 inference behind the LiveShift contract.

    Image codec and reference lookup stay injectable so the core transport layer
    does not depend on Pillow/OpenCV and identity profiles remain consent-gated.
    """

    def __init__(
        self,
        session: object,
        *,
        reference_provider: ReferenceProvider,
        decode_image: DecodeImage,
        encode_image: EncodeImage,
    ) -> None:
        self._session = session
        self._reference_provider = reference_provider
        self._decode_image = decode_image
        self._encode_image = encode_image

    def _transform(self, payload: bytes, profile_id: str) -> bytes:
        if not payload:
            raise ValueError("video frame payload is required")
        if not profile_id:
            raise ValueError("authorized face profile is required")

        source = self._decode_image(payload)
        reference = self._reference_provider(profile_id)
        outputs = self._session.run(
            ["transformed_image"],
            {
                "source_image": source,
                "reference_image": reference,
            },
        )
        if len(outputs) != 1:
            raise RuntimeError("Face v0.1 ONNX session returned an invalid output")
        return self._encode_image(outputs[0])

    async def transform_video(
        self, frame: MediaFrame, profile_id: str
    ) -> MediaFrame:
        payload = await asyncio.to_thread(self._transform, frame.payload, profile_id)
        return MediaFrame(payload=payload, timestamp_ms=frame.timestamp_ms)
