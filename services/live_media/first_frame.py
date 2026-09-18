"""First-visible-frame milestone for the Live AI Media Engine."""
from dataclasses import dataclass
from time import monotonic

from .inference_backend import FaceInferenceBackend
from .processors import MediaFrame


@dataclass(frozen=True)
class FirstFrameResult:
    frame: MediaFrame
    inference_ms: float
    transformed: bool


async def transform_first_frame(
    backend: FaceInferenceBackend,
    payload: bytes,
    profile_id: str,
    timestamp_ms: int,
) -> FirstFrameResult:
    if not payload:
        raise ValueError("video frame payload is required")
    if not profile_id:
        raise ValueError("authorized face profile is required")

    started = monotonic()
    source = MediaFrame(payload, timestamp_ms)
    output = await backend.transform_video(source, profile_id)
    elapsed_ms = (monotonic() - started) * 1000

    return FirstFrameResult(
        frame=output,
        inference_ms=elapsed_ms,
        transformed=output.payload != source.payload,
    )
