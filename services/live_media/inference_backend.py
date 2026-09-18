"""Backend contracts for authorized cloud face and voice transformations."""
from abc import ABC, abstractmethod

from .processors import MediaFrame


class FaceInferenceBackend(ABC):
    @abstractmethod
    async def transform_video(
        self, frame: MediaFrame, profile_id: str
    ) -> MediaFrame:
        raise NotImplementedError


class VoiceInferenceBackend(ABC):
    @abstractmethod
    async def transform_audio(
        self, frame: MediaFrame, profile_id: str
    ) -> MediaFrame:
        raise NotImplementedError
