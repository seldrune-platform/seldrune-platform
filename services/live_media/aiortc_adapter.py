"""Concrete aiortc signaling adapter for LiveShift.

aiortc is imported lazily so the core Seldrune API remains deployable without
the optional realtime-media dependency.
"""

from __future__ import annotations

from collections.abc import Callable

from .transport import MediaTransport
from .webrtc_adapter import IceCandidate, SessionDescription, WebRTCAdapter

TransportFactory = Callable[[object], MediaTransport]


class AiortcWebRTCAdapter(WebRTCAdapter):
    """Negotiate a peer connection and expose its bound Seldrune transport."""

    def __init__(
        self,
        *,
        transport_factory: TransportFactory,
        peer_connection: object | None = None,
    ) -> None:
        if peer_connection is None:
            try:
                from aiortc import RTCPeerConnection
            except ImportError as exc:
                raise RuntimeError(
                    "aiortc is required for the concrete WebRTC adapter"
                ) from exc
            peer_connection = RTCPeerConnection()
        self._peer = peer_connection
        self._transport_factory = transport_factory
        self._transport: MediaTransport | None = None

    async def accept_offer(
        self, offer: SessionDescription
    ) -> SessionDescription:
        try:
            from aiortc import RTCSessionDescription
        except ImportError as exc:
            raise RuntimeError(
                "aiortc is required for WebRTC session descriptions"
            ) from exc

        await self._peer.setRemoteDescription(
            RTCSessionDescription(sdp=offer.sdp, type=offer.type)
        )
        answer = await self._peer.createAnswer()
        await self._peer.setLocalDescription(answer)
        local = self._peer.localDescription
        if local is None:
            raise RuntimeError("WebRTC peer did not produce a local description")
        self._transport = self._transport_factory(self._peer)
        return SessionDescription(sdp=local.sdp, type=local.type)

    async def add_ice_candidate(self, candidate: IceCandidate) -> None:
        try:
            from aiortc.sdp import candidate_from_sdp
        except ImportError as exc:
            raise RuntimeError(
                "aiortc is required for WebRTC ICE candidates"
            ) from exc

        parsed = candidate_from_sdp(candidate.candidate)
        parsed.sdpMid = candidate.sdp_mid
        parsed.sdpMLineIndex = candidate.sdp_mline_index
        await self._peer.addIceCandidate(parsed)

    async def transport(self) -> MediaTransport:
        if self._transport is None:
            raise RuntimeError("WebRTC offer must be accepted before transport")
        return self._transport

    async def close(self) -> None:
        if self._transport is not None:
            await self._transport.close()
        await self._peer.close()
