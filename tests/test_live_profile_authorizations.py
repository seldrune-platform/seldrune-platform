from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.core.config import settings
from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]

_SERVICE_TOKEN = "seldrune-live-profile-auth-test-token-0001"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _request(client, base: str, headers: dict[str, str], kind: str, profile_id: str):
    return client.post(
        f"{base}/profile-authorizations",
        headers=headers,
        json={
            "profile_kind": kind,
            "profile_id": profile_id,
            "evidence_reference": f"vault://consent/{profile_id}",
            "evidence_sha256": "a" * 64,
            "expires_at": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
        },
    )


def _service_check(client, organization_id: str, user_id: str, **changes):
    payload = {
        "organization_id": organization_id,
        "user_id": user_id,
        "face_profile_id": "face-approved",
        "voice_profile_id": "voice-approved",
    }
    payload.update(changes)
    return client.post(
        "/api/v1/internal/live-media/profile-authorization-check",
        headers={"Authorization": f"Bearer {_SERVICE_TOKEN}"},
        json=payload,
    )


def test_profile_grants_require_independent_review_and_can_be_revoked(client, monkeypatch):
    monkeypatch.setattr(settings, "live_profile_authorizer_token", _SERVICE_TOKEN)
    owner_token, organization_id = register_owner(client)
    owner_headers = _headers(owner_token)
    owner_user_id = client.get("/api/v1/auth/me", headers=owner_headers).json()["user"]["id"]
    base = f"/api/v1/organizations/{organization_id}/liveshift"

    face = _request(client, base, owner_headers, "face", "face-approved")
    voice = _request(client, base, owner_headers, "voice", "voice-approved")
    assert face.status_code == 201
    assert voice.status_code == 201
    assert face.json()["status"] == "pending"
    assert _service_check(client, organization_id, owner_user_id).json() == {
        "face_profile_authorized": False,
        "voice_profile_authorized": False,
    }

    self_approval = client.post(
        f"{base}/profile-authorizations/{face.json()['id']}/review",
        headers=owner_headers,
        json={
            "decision": "approve",
            "evidence_reviewed": True,
            "subject_consent_verified": True,
        },
    )
    assert self_approval.status_code == 403

    admin_invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=owner_headers,
        json={"email": "profile-reviewer@example.com", "role": "admin"},
    )
    assert admin_invitation.status_code == 201
    admin_acceptance = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": admin_invitation.json()["token"],
            "display_name": "Profile Reviewer",
            "password": "profile-reviewer-password-123",
        },
    )
    assert admin_acceptance.status_code == 201
    admin_headers = _headers(admin_acceptance.json()["access_token"])

    for item in (face, voice):
        approved = client.post(
            f"{base}/profile-authorizations/{item.json()['id']}/review",
            headers=admin_headers,
            json={
                "decision": "approve",
                "evidence_reviewed": True,
                "subject_consent_verified": True,
            },
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["reviewed_by_user_id"]

    assert _service_check(client, organization_id, owner_user_id).json() == {
        "face_profile_authorized": True,
        "voice_profile_authorized": True,
    }
    assert _service_check(client, organization_id, str(uuid4())).json() == {
        "face_profile_authorized": False,
        "voice_profile_authorized": False,
    }

    revoked = client.delete(
        f"{base}/profile-authorizations/{face.json()['id']}",
        headers=owner_headers,
    )
    assert revoked.status_code == 204
    assert _service_check(client, organization_id, owner_user_id).json() == {
        "face_profile_authorized": False,
        "voice_profile_authorized": True,
    }


def test_profile_request_and_review_reject_invalid_evidence_and_expiry(client):
    owner_token, organization_id = register_owner(client)
    headers = _headers(owner_token)
    base = f"/api/v1/organizations/{organization_id}/liveshift/profile-authorizations"

    invalid_hash = client.post(
        base,
        headers=headers,
        json={
            "profile_kind": "face",
            "profile_id": "face-invalid",
            "evidence_reference": "vault://consent/one",
            "evidence_sha256": "not-a-hash",
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    assert invalid_hash.status_code == 422

    too_late = client.post(
        base,
        headers=headers,
        json={
            "profile_kind": "face",
            "profile_id": "face-too-late",
            "evidence_reference": "vault://consent/two",
            "evidence_sha256": "b" * 64,
            "expires_at": (datetime.now(UTC) + timedelta(days=366)).isoformat(),
        },
    )
    assert too_late.status_code == 422

    requested = _request(
        client,
        f"/api/v1/organizations/{organization_id}/liveshift",
        headers,
        "face",
        "face-review",
    )
    assert requested.status_code == 201
    missing_attestation = client.post(
        f"{base}/{requested.json()['id']}/review",
        headers=headers,
        json={"decision": "approve"},
    )
    assert missing_attestation.status_code == 422


def test_internal_profile_authorizer_is_fail_closed_without_service_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "live_profile_authorizer_token", None)
    response = client.post(
        "/api/v1/internal/live-media/profile-authorization-check",
        json={
            "organization_id": str(uuid4()),
            "user_id": str(uuid4()),
            "face_profile_id": "face",
            "voice_profile_id": "voice",
        },
    )
    assert response.status_code == 503


def test_profile_registry_page_is_served(client):
    page = client.get("/liveshell/profiles")
    script = client.get("/console-assets/liveshell-profiles.js")
    assert page.status_code == 200
    assert "Profile authorization" in page.text
    assert script.status_code == 200
    assert "independently verified the subject consent" in script.text
