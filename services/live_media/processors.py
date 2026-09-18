from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class MediaFrame:
    payload: bytes
    timestamp_ms: int

class VideoProcessor(ABC):
    @abstractmethod
    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame: ...

class AudioProcessor(ABC):
    @abstractmethod
    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame: ...

class PassthroughVideoProcessor(VideoProcessor):
    async def process(self, frame, profile_id): return frame

class PassthroughAudioProcessor(AudioProcessor):
    async def process(self, frame, profile_id): return frame
