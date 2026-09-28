"""Mobile LiveShell page and authenticated WebRTC GPU-gateway bridge."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote, urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from backend.app.api.dependencies import require_org_permission
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
page_router = APIRouter(tags=["liveshell-mobile"])
api_router = APIRouter(prefix="/organizations", tags=["liveshell-mobile"])

live_run_dependency = require_org_permission(Permission.AGENTS_RUN)
LiveRunDep = Annotated[Membership, Depends(live_run_dependency)]


@page_router.get("/liveshell/mobile", include_in_schema=False)
def liveshell_mobile_page() -> FileResponse:
    return FileResponse(
        WEB_ROOT / "liveshell-mobile.html",
        headers={"Cache-Control": "no-store"},
    )


class WebRTCOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["offer"]
    sdp: str = Field(min_length=20, max_length=250_000)


class LiveSessionOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offer: WebRTCOffer
    face_profile_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    voice_profile_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    consent_confirmed: bool = False
    synthetic_media_indicator_enabled: bool = False
    video_resolution: Literal["720p", "1080p"] = "720p"
    target_accelerator_profile: Literal["rtx-4090", "rtx-5090", "rtx-pro-6000-blackwell"] = "rtx-4090"


class GatewayDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["answer"]
    sdp: str = Field(min_length=20, max_length=250_000)


class GatewaySession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    answer: GatewayDescription
    face_profile_id: str
    voice_profile_id: str
    face_profile_authorized: StrictBool
    voice_profile_authorized: StrictBool
    synthetic_media_indicator_enabled: StrictBool
    actual_accelerator_profile: Literal[
        "rtx-4090", "rtx-5090", "rtx-pro-6000-blackwell"
    ] | None = None
    output_width: int | None = Field(default=None, ge=1, le=7680)
    output_height: int | None = Field(default=None, ge=1, le=4320)
    audio_sample_rate_hz: int | None = Field(default=None, ge=1, le=192_000)
    output_fps: float | None = Field(default=None, ge=1, le=120)


def _gateway_configuration(
    *,
    url_env: str = "SELDRUNE_LIVESHIFT_WORKER_URL",
    token_env: str = "SELDRUNE_LIVESHIFT_WORKER_TOKEN",
    feature_name: str = "LiveShell GPU session gateway",
) -> tuple[str, str]:
    base_url = os.getenv(url_env, "").strip().rstrip("/")
    token = os.getenv(token_env, "").strip()
    if not base_url or not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The {feature_name} is not configured.",
        )

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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The {feature_name} URL must use HTTPS or a private service URL.",
        )
    return base_url, token


def _parse_gateway_session(
    payload: LiveSessionOffer,
    value: object,
) -> GatewaySession:
    try:
        result = GatewaySession.model_validate(value)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LiveShell GPU gateway returned an invalid session response.",
        ) from exc

    if (
        result.face_profile_id != payload.face_profile_id
        or result.voice_profile_id != payload.voice_profile_id
        or not result.face_profile_authorized
        or not result.voice_profile_authorized
        or not result.synthetic_media_indicator_enabled
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The LiveShell GPU gateway did not verify both authorized profiles "
                "and the synthetic-media indicator."
            ),
        )
    return result


async def _release_gateway_session(
    base_url: str,
    token: str,
    organization_id: UUID,
    user_id: UUID,
    session_id: str,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            await client.delete(
                f"{base_url}/v1/sessions/{quote(session_id, safe='')}",
                params={
                    "organization_id": str(organization_id),
                    "user_id": str(user_id),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        return


@api_router.get("/{organization_id}/liveshift/live/readiness")
def liveshell_live_readiness(
    organization_id: UUID,
    _membership: LiveRunDep,
) -> dict[str, object]:
    """Report gateway configuration without claiming a model or GPU is online."""
    try:
        _gateway_configuration()
    except HTTPException:
        return {
            "gateway_configured": False,
            "video_target": "1280x720 at 30 fps",
            "audio_target_sample_rate_hz": 48_000,
            "accelerator_targets": ["rtx-4090", "rtx-5090", "rtx-pro-6000-blackwell"],
            "production_evidence_required": True,
        }
    return {
        "gateway_configured": True,
        "video_target": "1280x720 at 30 fps",
        "audio_target_sample_rate_hz": 48_000,
        "accelerator_targets": ["rtx-4090", "rtx-5090", "rtx-pro-6000-blackwell"],
        "production_evidence_required": True,
        "note": "Configuration is not proof that a worker, model, or HD stream is ready.",
    }


@api_router.post("/{organization_id}/liveshift/live/sessions")
async def create_liveshell_live_session(
    organization_id: UUID,
    payload: LiveSessionOffer,
    membership: LiveRunDep,
) -> dict[str, object]:
    """Forward authenticated WebRTC signaling to the private GPU session gateway."""
    if not payload.consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Consent for both enrolled identity profiles is required.",
        )
    if not payload.synthetic_media_indicator_enabled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The synthetic-media indicator must remain enabled.",
        )

    base_url, token = _gateway_configuration()
    request_body = {
        "organization_id": str(organization_id),
        "user_id": str(membership.user_id),
        "offer": payload.offer.model_dump(),
        "face_profile_id": payload.face_profile_id,
        "voice_profile_id": payload.voice_profile_id,
        "consent_confirmed": True,
        "synthetic_media_indicator_enabled": True,
        "video_resolution": payload.video_resolution,
        "audio_sample_rate_hz": 48_000,
        "target_accelerator_profile": payload.target_accelerator_profile,
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=3.0),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"{base_url}/v1/sessions",
                json=request_body,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The LiveShell GPU gateway timed out while starting the session.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LiveShell GPU gateway could not be reached.",
        ) from exc

    if response.status_code not in {200, 201}:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LiveShell GPU gateway rejected the session request.",
        )
    try:
        gateway_payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LiveShell GPU gateway returned an invalid session response.",
        ) from exc

    try:
        gateway_session = _parse_gateway_session(payload, gateway_payload)
    except HTTPException:
        if isinstance(gateway_payload, dict):
            session_id = gateway_payload.get("session_id")
            if isinstance(session_id, str) and re.fullmatch(
                r"[A-Za-z0-9_-]{1,128}", session_id
            ):
                await _release_gateway_session(
                    base_url,
                    token,
                    organization_id,
                    membership.user_id,
                    session_id,
                )
        raise

    return {
        "session_id": gateway_session.session_id,
        "answer": gateway_session.answer.model_dump(),
        "face_profile_id": gateway_session.face_profile_id,
        "voice_profile_id": gateway_session.voice_profile_id,
        "synthetic_media_indicator_enabled": True,
        "actual_accelerator_profile": gateway_session.actual_accelerator_profile,
        "output": {
            "width": gateway_session.output_width,
            "height": gateway_session.output_height,
            "audio_sample_rate_hz": gateway_session.audio_sample_rate_hz,
            "fps": gateway_session.output_fps,
        },
    }


@api_router.delete(
    "/{organization_id}/liveshift/live/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
)
async def close_liveshell_live_session(
    organization_id: UUID,
    session_id: str,
    membership: LiveRunDep,
) -> dict[str, bool]:
    """Close a session only for its authenticated organization and user."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LiveShell session not found.",
        )

    base_url, token = _gateway_configuration()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False,
        ) as client:
            response = await client.delete(
                f"{base_url}/v1/sessions/{quote(session_id, safe='')}",
                params={
                    "organization_id": str(organization_id),
                    "user_id": str(membership.user_id),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The LiveShell GPU gateway timed out while closing the session.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LiveShell GPU gateway could not be reached.",
        ) from exc

    if response.status_code not in {200, 202, 204, 404}:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LiveShell GPU gateway could not close the session.",
        )
    return {"closed": True}
