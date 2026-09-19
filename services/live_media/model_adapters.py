"""Provider-neutral adapters for authorized live media transforms.

Concrete GPU implementations plug in here. Keeping model code behind these
interfaces lets Seldrune use CUDA/TensorRT/ONNX or hosted GPU workers without
changing session or WebRTC code.
"""

from dataclasses import dataclass

from .inference_backend import FaceInferenceBackend, VoiceInferenceBackend
from .processors import AudioProcessor, MediaFrame, VideoProcessor


@dataclass(frozen=True)
class InferenceContext:
    session_id: str
    consent_token: str
    synthetic_media_indicator: bool = True


class AuthorizedFaceAdapter(VideoProcessor):
    def __init__(self, backend: FaceInferenceBackend) -> None:
        self.backend = backend

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        return await self.backend.transform_video(frame, profile_id)


class AuthorizedVoiceAdapter(AudioProcessor):
    def __init__(self, backend: VoiceInferenceBackend) -> None:
        self.backend = backend

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        return await self.backend.transform_audio(frame, profile_id)
