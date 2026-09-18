"""Provider-neutral WebRTC adapter boundary.

A concrete aiortc/native/SFU implementation can implement this interface
without coupling Seldrune's session orchestration to one WebRTC library.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .transport import MediaTransport


@dataclass(frozen=True)
class SessionDescription:
    sdp: str
    type: str


@dataclass(frozen=True)
class IceCandidate:
    candidate: str
    sdp_mid: str | None = None
    sdp_mline_index: int | None = None


class WebRTCAdapter(ABC):
    @abstractmethod
    async def accept_offer(
        self, offer: SessionDescription
    ) -> SessionDescription:
        raise NotImplementedError

    @abstractmethod
    async def add_ice_candidate(self, candidate: IceCandidate) -> None:
        raise NotImplementedError

    @abstractmethod
    async def transport(self) -> MediaTransport:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
