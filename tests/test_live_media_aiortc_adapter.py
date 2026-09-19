import asyncio
import sys
import types

import pytest

from services.live_media.aiortc_adapter import AiortcWebRTCAdapter
from services.live_media.transport import MediaTransport
from services.live_media.webrtc_adapter import IceCandidate, SessionDescription


class _Transport(MediaTransport):
    def __init__(self):
        self.closed = False

    async def recv_video(self):
        raise NotImplementedError

    async def recv_audio(self):
        raise NotImplementedError

    async def send_video(self, frame):
        raise NotImplementedError

    async def send_audio(self, frame):
        raise NotImplementedError

    async def close(self):
        self.closed = True


class _Description:
    def __init__(self, sdp, type):
        self.sdp = sdp
        self.type = type


class _Peer:
    def __init__(self):
        self.remote = None
        self.localDescription = None
        self.candidate = None
        self.closed = False

    async def setRemoteDescription(self, description):
        self.remote = description

    async def createAnswer(self):
        return _Description("answer-sdp", "answer")

    async def setLocalDescription(self, description):
        self.localDescription = description

    async def addIceCandidate(self, candidate):
        self.candidate = candidate

    async def close(self):
        self.closed = True


def _install_fake_aiortc(monkeypatch):
    module = types.ModuleType("aiortc")
    module.RTCSessionDescription = _Description
    sdp = types.ModuleType("aiortc.sdp")

    def candidate_from_sdp(value):
        candidate = types.SimpleNamespace(value=value)
        candidate.sdpMid = None
        candidate.sdpMLineIndex = None
        return candidate

    sdp.candidate_from_sdp = candidate_from_sdp
    monkeypatch.setitem(sys.modules, "aiortc", module)
    monkeypatch.setitem(sys.modules, "aiortc.sdp", sdp)


def test_aiortc_adapter_negotiates_and_binds_transport(monkeypatch):
    _install_fake_aiortc(monkeypatch)
    peer = _Peer()
    transport = _Transport()
    adapter = AiortcWebRTCAdapter(
        peer_connection=peer,
        transport_factory=lambda _: transport,
    )

    answer = asyncio.run(
        adapter.accept_offer(SessionDescription("offer-sdp", "offer"))
    )

    assert answer == SessionDescription("answer-sdp", "answer")
    assert peer.remote.sdp == "offer-sdp"
    assert asyncio.run(adapter.transport()) is transport

    asyncio.run(
        adapter.add_ice_candidate(
            IceCandidate("candidate-data", "video", 0)
        )
    )
    assert peer.candidate.sdpMid == "video"
    assert peer.candidate.sdpMLineIndex == 0

    asyncio.run(adapter.close())
    assert transport.closed is True
    assert peer.closed is True


def test_aiortc_transport_requires_accepted_offer():
    adapter = AiortcWebRTCAdapter(
        peer_connection=_Peer(),
        transport_factory=lambda _: _Transport(),
    )
    with pytest.raises(RuntimeError, match="offer must be accepted"):
        asyncio.run(adapter.transport())
