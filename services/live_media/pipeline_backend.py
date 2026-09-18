"""Adapter from a licensed byte-oriented face transform to Seldrune's backend API."""

from collections.abc import Awaitable, Callable

from .inference_backend import FaceInferenceBackend
from .processors import MediaFrame
from .video_inference_pipeline import VideoInferenceMetrics, VideoInferencePipeline

LicensedFaceTransform = Callable[[bytes, str], Awaitable[bytes]]


class PipelineFaceInferenceBackend(FaceInferenceBackend):
    """Run an authorized face transform through the measured video pipeline."""

    def __init__(
        self,
        transform: LicensedFaceTransform,
        *,
        preprocess: Callable[[bytes], bytes] | None = None,
        composite: Callable[[bytes, bytes], bytes] | None = None,
    ) -> None:
        self._pipeline = VideoInferencePipeline(
            transform,
            preprocess=preprocess,
            composite=composite,
        )
        self.last_metrics: VideoInferenceMetrics | None = None

    async def transform_video(
        self, frame: MediaFrame, profile_id: str
    ) -> MediaFrame:
        result = await self._pipeline.run(frame, profile_id)
        self.last_metrics = result.metrics
        return result.frame
