"""Model-neutral stages for authorized video inference.

These helpers deliberately contain no model weights or provider-specific code.
A licensed face backend can plug into the transform stage without changing the
WebRTC/session pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from collections.abc import Awaitable, Callable

from .processors import MediaFrame

FrameTransform = Callable[[bytes, str], Awaitable[bytes]]


@dataclass(frozen=True)
class VideoInferenceMetrics:
    preprocess_ms: float
    inference_ms: float
    composite_ms: float
    total_ms: float


@dataclass(frozen=True)
class VideoInferenceResult:
    frame: MediaFrame
    metrics: VideoInferenceMetrics
    transformed: bool


class VideoInferencePipeline:
    """Execute preprocessing, licensed inference, and compositing in order."""

    def __init__(
        self,
        transform: FrameTransform,
        *,
        preprocess: Callable[[bytes], bytes] | None = None,
        composite: Callable[[bytes, bytes], bytes] | None = None,
    ) -> None:
        self._transform = transform
        self._preprocess = preprocess or (lambda payload: payload)
        self._composite = composite or (lambda _source, transformed: transformed)

    async def run(self, frame: MediaFrame, profile_id: str) -> VideoInferenceResult:
        if not frame.payload:
            raise ValueError("video frame payload is required")
        if not profile_id:
            raise ValueError("authorized face profile is required")

        total_started = monotonic()

        started = monotonic()
        prepared = self._preprocess(frame.payload)
        preprocess_ms = (monotonic() - started) * 1000

        started = monotonic()
        transformed = await self._transform(prepared, profile_id)
        inference_ms = (monotonic() - started) * 1000
        if not transformed:
            raise ValueError("face backend returned an empty frame")

        started = monotonic()
        output = self._composite(frame.payload, transformed)
        composite_ms = (monotonic() - started) * 1000

        metrics = VideoInferenceMetrics(
            preprocess_ms=preprocess_ms,
            inference_ms=inference_ms,
            composite_ms=composite_ms,
            total_ms=(monotonic() - total_started) * 1000,
        )
        return VideoInferenceResult(
            frame=MediaFrame(output, frame.timestamp_ms),
            metrics=metrics,
            transformed=output != frame.payload,
        )
