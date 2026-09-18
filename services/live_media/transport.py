"""Transport interfaces used by WebRTC/media gateway implementations."""
from abc import ABC, abstractmethod

from .processors import MediaFrame


class MediaTransport(ABC):
    @abstractmethod
    async def recv_video(self) -> MediaFrame:
        raise NotImplementedError

    @abstractmethod
    async def recv_audio(self) -> MediaFrame:
        raise NotImplementedError

    @abstractmethod
    async def send_video(self, frame: MediaFrame) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_audio(self, frame: MediaFrame) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
