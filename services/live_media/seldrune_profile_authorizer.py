from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx

from .webrtc_gateway import ProfileAuthorization

_AUTHORIZATION_PATH = "/api/v1/internal/live-media/profile-authorization-check"


def _authorization_service() -> tuple[str, str]:
    base_url = os.getenv("SELDRUNE_PROFILE_AUTHORIZATION_URL", "").strip().rstrip("/")
    token = os.getenv("SELDRUNE_PROFILE_AUTHORIZATION_TOKEN", "").strip()
    parsed = urlsplit(base_url)
    hostname = (parsed.hostname or "").lower()
    private_http = parsed.scheme == "http" and (
        hostname.endswith(".internal")
        or hostname in {"localhost", "127.0.0.1", "::1"}
    )
    if (
        not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not private_http)
    ):
        raise RuntimeError(
            "SELDRUNE_PROFILE_AUTHORIZATION_URL must use HTTPS or a private service URL"
        )
    if len(token.encode("utf-8")) < 32:
        raise RuntimeError(
            "SELDRUNE_PROFILE_AUTHORIZATION_TOKEN must contain at least 32 bytes"
        )
    return base_url, token


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=3.0, follow_redirects=False)


async def authorize_profiles(
    organization_id: str,
    user_id: str,
    face_profile_id: str,
    voice_profile_id: str,
) -> ProfileAuthorization:
    """Check current profile grants against Seldrune's reviewed registry."""
    base_url, token = _authorization_service()
    payload = {
        "organization_id": organization_id,
        "user_id": user_id,
        "face_profile_id": face_profile_id,
        "voice_profile_id": voice_profile_id,
    }
    try:
        async with _client() as client:
            response = await client.post(
                f"{base_url}{_AUTHORIZATION_PATH}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Seldrune profile authorization check failed") from exc

    if not isinstance(result, dict):
        raise RuntimeError("Seldrune returned an invalid profile authorization response")
    face = result.get("face_profile_authorized")
    voice = result.get("voice_profile_authorized")
    if type(face) is not bool or type(voice) is not bool:
        raise RuntimeError("Seldrune returned an invalid profile authorization response")
    return ProfileAuthorization(
        face_profile_authorized=face,
        voice_profile_authorized=voice,
    )
