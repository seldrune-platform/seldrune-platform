from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MediaFrame:
    payload: bytes
    timestamp_ms: int


class VideoProcessor(ABC):
    @abstractmethod
    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        raise NotImplementedError


class AudioProcessor(ABC):
    @abstractmethod
    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        raise NotImplementedError


class PassthroughVideoProcessor(VideoProcessor):
    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        return frame


class PassthroughAudioProcessor(AudioProcessor):
    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        return frame
