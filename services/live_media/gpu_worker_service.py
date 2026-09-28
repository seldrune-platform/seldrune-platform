"""Transport-neutral execution service hosted by each GPU worker."""
from dataclasses import dataclass
from time import perf_counter_ns

from .inference_backend import FaceInferenceBackend, VoiceInferenceBackend
from .processors import MediaFrame
from .worker_protocol import InferenceRequest, InferenceResult, MediaKind


@dataclass
class GPUWorkerService:
    face: FaceInferenceBackend
    voice: VoiceInferenceBackend

    async def infer(self, request: InferenceRequest) -> InferenceResult:
        started_ns = perf_counter_ns()
        frame = MediaFrame(request.payload, request.timestamp_ms)
        if request.media_kind == MediaKind.VIDEO:
            output = await self.face.transform_video(frame, request.profile_id)
        else:
            output = await self.voice.transform_audio(frame, request.profile_id)
        inference_ms = max(0.0, (perf_counter_ns() - started_ns) / 1_000_000.0)
        return InferenceResult(
            request_id=request.request_id,
            timestamp_ms=output.timestamp_ms,
            payload=output.payload,
            inference_ms=inference_ms,
        )

