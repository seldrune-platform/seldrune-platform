"""Desktop virtual-device bridge contracts."""
from abc import ABC, abstractmethod


class VirtualCameraBridge(ABC):
    @abstractmethod
    async def publish_video(self, frame: bytes, timestamp_ms: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class VirtualMicrophoneBridge(ABC):
    @abstractmethod
    async def publish_audio(self, chunk: bytes, timestamp_ms: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
