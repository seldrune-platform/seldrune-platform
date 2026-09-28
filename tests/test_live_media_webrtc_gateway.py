from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from services.live_media.webrtc_gateway import (
    CreateSessionRequest,
    GatewaySettings,
    GatewayUnavailable,
    IceServer,
    LiveMediaGateway,
    ProfileAuthorization,
    create_app,
)
from services.live_media.runpod_live_transport import verify_session_ticket

HTTP_TOKEN = "h" * 40
WORKER_TOKEN = "w" * 40
TICKET_SECRET = "s" * 48


class FakePeer:
    def __init__(self):
        self.handlers = {}
        self.tracks = []
        self.localDescription = None
        self.connectionState = "new"
        self.closed = False

    def on(self, name, handler):
        self.handlers[name] = handler

    def addTrack(self, track):
        self.tracks.append(track)

    async def setRemoteDescription(self, _description):
        for kind in ("video", "audio"):
            self.handlers["track"](SimpleNamespace(kind=kind))

    async def createAnswer(self):
        return SimpleNamespace(sdp="v=0\\r\\n" + "a=answer\\r\\n" * 3, type="answer")

    async def setLocalDescription(self, answer):
        self.localDescription = answer

    async def close(self):
        self.closed = True
        self.connectionState = "closed"


class FakeWorkerSession:
    def __init__(self, *, strict=True, accelerator="rtx-4090"):
        self.client = SimpleNamespace(
            require_realism_evidence=strict,
            actual_accelerator_profile=accelerator,
        )
        self.pipeline = object()
        self.closed = False

    async def close(self):
        self.closed = True


def request(**changes):
    values = {
        "organization_id": "org-1",
        "user_id": "user-1",
        "offer": {"type": "offer", "sdp": "v=0\\r\\n" + "a=offer\\r\\n" * 3},
        "face_profile_id": "face-1",
        "voice_profile_id": "voice-1",
        "consent_confirmed": True,
        "synthetic_media_indicator_enabled": True,
        "video_resolution": "1080p",
        "target_accelerator_profile": "rtx-4090",
    }
    values.update(changes)
    return CreateSessionRequest.model_validate(values)


def settings(**changes):
    values = {
        "http_service_token": HTTP_TOKEN,
        "worker_service_token": WORKER_TOKEN,
        "ticket_secret": TICKET_SECRET,
        "worker_host": "worker.internal",
        "worker_port": 8765,
        "worker_tls_server_name": "worker.internal",
        "worker_region": "us-east",
        "ice_servers": [IceServer(["stun:stun.example.test:3478"])],
        "max_sessions": 1,
        "max_inflight": 2,
    }
    values.update(changes)
    return GatewaySettings(**values)


def gateway_for(peer, worker, authorizer=None):
    seen = {}

    async def connect_worker(**kwargs):
        seen.update(kwargs)
        return worker

    return LiveMediaGateway(
        settings(),
        profile_authorizer=authorizer or (lambda *_: ProfileAuthorization(True, True)),
        worker_session_factory=connect_worker,
        peer_factory=lambda _ice: peer,
        description_factory=lambda sdp, kind: SimpleNamespace(sdp=sdp, type=kind),
    ), seen


def test_gateway_binds_authorized_profiles_to_ticket_and_two_webrtc_tracks():
    async def scenario():
        peer = FakePeer()
        worker = FakeWorkerSession()
        gateway, seen = gateway_for(peer, worker)

        result = await gateway.create(request())

        claims = verify_session_ticket(seen["ticket"], TICKET_SECRET)
        assert claims.organization_id == "org-1"
        assert claims.user_id == "user-1"
        assert claims.face_profile_id == "face-1"
        assert claims.voice_profile_id == "voice-1"
        assert claims.face_consent_verified and claims.voice_consent_verified
        assert result.session_ticket_validated
        assert result.runpod_session_connected
        assert result.realism_evidence_required
        assert result.actual_accelerator_profile == "rtx-4090"
        assert result.answer.type == "answer"
        assert {track.kind for track in peer.tracks} == {"audio", "video"}
        assert result.output_width is None
        assert result.output_fps is None

        session_id = result.session_id
        assert await gateway.close(
            session_id, organization_id="other-org", user_id="user-1"
        ) is False
        assert not worker.closed
        assert await gateway.close(
            session_id, organization_id="org-1", user_id="user-1"
        ) is True
        assert worker.closed and peer.closed

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes",
    [
        {"consent_confirmed": False},
        {"synthetic_media_indicator_enabled": False},
    ],
)
def test_gateway_rejects_missing_consent_before_connecting(changes):
    async def scenario():
        worker_calls = []

        async def connect_worker(**kwargs):
            worker_calls.append(kwargs)
            return FakeWorkerSession()

        gateway = LiveMediaGateway(
            settings(),
            profile_authorizer=lambda *_: ProfileAuthorization(True, True),
            worker_session_factory=connect_worker,
            peer_factory=lambda _ice: FakePeer(),
            description_factory=lambda sdp, kind: SimpleNamespace(sdp=sdp, type=kind),
        )
        with pytest.raises(PermissionError):
            await gateway.create(request(**changes))
        assert worker_calls == []

    asyncio.run(scenario())


def test_gateway_fails_closed_without_profile_authorization():
    async def scenario():
        worker_calls = []

        async def connect_worker(**kwargs):
            worker_calls.append(kwargs)
            return FakeWorkerSession()

        gateway = LiveMediaGateway(
            settings(),
            profile_authorizer=lambda *_: ProfileAuthorization(True, False),
            worker_session_factory=connect_worker,
            peer_factory=lambda _ice: FakePeer(),
            description_factory=lambda sdp, kind: SimpleNamespace(sdp=sdp, type=kind),
        )
        with pytest.raises(PermissionError, match="both profiles"):
            await gateway.create(request())
        assert worker_calls == []

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "worker",
    [
        FakeWorkerSession(strict=False),
        FakeWorkerSession(accelerator="rtx-5090"),
    ],
)
def test_gateway_rejects_unattested_quality_or_wrong_accelerator(worker):
    async def scenario():
        peer = FakePeer()
        gateway, _ = gateway_for(peer, worker)
        with pytest.raises(GatewayUnavailable):
            await gateway.create(request())
        assert worker.closed
        assert peer.closed is False

    asyncio.run(scenario())


def test_gateway_http_token_protects_create_and_delete():
    peer = FakePeer()
    worker = FakeWorkerSession()
    gateway, _ = gateway_for(peer, worker)
    app = create_app(gateway)
    body = request().model_dump(mode="json")

    with TestClient(app) as client:
        denied = client.post("/v1/sessions", json=body)
        accepted = client.post(
            "/v1/sessions",
            json=body,
            headers={"Authorization": f"Bearer {HTTP_TOKEN}"},
        )
        session_id = accepted.json()["session_id"]
        wrong_owner = client.delete(
            f"/v1/sessions/{session_id}",
            params={"organization_id": "other-org", "user_id": "user-1"},
            headers={"Authorization": f"Bearer {HTTP_TOKEN}"},
        )
        closed = client.delete(
            f"/v1/sessions/{session_id}",
            params={"organization_id": "org-1", "user_id": "user-1"},
            headers={"Authorization": f"Bearer {HTTP_TOKEN}"},
        )

    assert denied.status_code == 401
    assert accepted.status_code == 201
    assert accepted.json()["session_ticket_validated"] is True
    assert wrong_owner.status_code == 404
    assert closed.status_code == 200
    assert worker.closed and peer.closed
