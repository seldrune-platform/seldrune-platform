"""Provider-neutral adapters for authorized live media transforms.

Concrete GPU implementations plug in here. Keeping model code behind these
interfaces lets Seldrune use CUDA/TensorRT/ONNX or hosted GPU workers without
changing session or WebRTC code.
"""
from dataclasses import dataclass
from .processors import MediaFrame, VideoProcessor, AudioProcessor

@dataclass(frozen=True)
class InferenceContext:
    session_id:str
    consent_token:str
    synthetic_media_indicator:bool=True

class AuthorizedFaceAdapter(VideoProcessor):
    def __init__(self, backend): self.backend=backend
    async def process(self, frame:MediaFrame, profile_id:str)->MediaFrame:
        payload=await self.backend.transform_video(frame.payload, profile_id)
        return MediaFrame(payload=payload,timestamp_ms=frame.timestamp_ms)

class AuthorizedVoiceAdapter(AudioProcessor):
    def __init__(self, backend): self.backend=backend
    async def process(self, frame:MediaFrame, profile_id:str)->MediaFrame:
        payload=await self.backend.transform_audio(frame.payload, profile_id)
        return MediaFrame(payload=payload,timestamp_ms=frame.timestamp_ms)
