import asyncio

import httpx
import pytest

from services.live_media import seldrune_profile_authorizer as authorizer

_TOKEN = "seldrune-profile-auth-adapter-test-token-0001"


def _env(monkeypatch):
    monkeypatch.setenv("SELDRUNE_PROFILE_AUTHORIZATION_URL", "https://api.example.test")
    monkeypatch.setenv("SELDRUNE_PROFILE_AUTHORIZATION_TOKEN", _TOKEN)


def test_authorizer_uses_tls_service_and_returns_both_grants(monkeypatch):
    _env(monkeypatch)
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["json"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "face_profile_authorized": True,
                "voice_profile_authorized": False,
            },
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        authorizer,
        "_client",
        lambda: httpx.AsyncClient(transport=transport, timeout=3, follow_redirects=False),
    )
    result = asyncio.run(
        authorizer.authorize_profiles("org-1", "user-1", "face-1", "voice-1")
    )
    assert seen["url"] == (
        "https://api.example.test/api/v1/internal/live-media/profile-authorization-check"
    )
    assert seen["authorization"] == f"Bearer {_TOKEN}"
    assert '"organization_id":"org-1"' in seen["json"]
    assert result.face_profile_authorized is True
    assert result.voice_profile_authorized is False


@pytest.mark.parametrize(
    ("url", "token"),
    [
        ("", _TOKEN),
        ("http://public.example.test", _TOKEN),
        ("https://api.example.test", "short"),
    ],
)
def test_authorizer_rejects_missing_or_unsafe_configuration(monkeypatch, url, token):
    monkeypatch.setenv("SELDRUNE_PROFILE_AUTHORIZATION_URL", url)
    monkeypatch.setenv("SELDRUNE_PROFILE_AUTHORIZATION_TOKEN", token)
    with pytest.raises(RuntimeError):
        asyncio.run(authorizer.authorize_profiles("org", "user", "face", "voice"))


def test_authorizer_rejects_malformed_service_response(monkeypatch):
    _env(monkeypatch)
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"face_profile_authorized": 1})
    )
    monkeypatch.setattr(
        authorizer,
        "_client",
        lambda: httpx.AsyncClient(transport=transport, timeout=3, follow_redirects=False),
    )
    with pytest.raises(RuntimeError):
        asyncio.run(authorizer.authorize_profiles("org", "user", "face", "voice"))
