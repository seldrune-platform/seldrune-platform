from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MediaFrame:
    payload: bytes
    timestamp_ms: int
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None


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
