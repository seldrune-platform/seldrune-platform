from __future__ import annotations

import hmac
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.api.dependencies import (
    CurrentUserDep,
    SessionDep,
    require_org_permission,
)
from backend.app.core.config import settings
from backend.app.core.rbac import Permission, has_permission
from backend.app.models.live_profile_authorization import LiveProfileAuthorization
from backend.app.models.membership import Membership
from backend.app.schemas.live_profile_authorization import (
    ProfileAuthorizationCheck,
    ProfileAuthorizationCheckResult,
    ProfileAuthorizationPublic,
    ProfileAuthorizationRequest,
    ProfileAuthorizationReview,
)
from backend.app.services.audit import record_audit

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
page_router = APIRouter(tags=["liveshell-profile-authorizations"])
router = APIRouter(tags=["liveshell-profile-authorizations"])
internal_router = APIRouter(tags=["internal-live-profile-authorization"])

live_run_dependency = require_org_permission(Permission.AGENTS_RUN)
manage_membership_dependency = require_org_permission(Permission.MEMBERS_MANAGE)
LiveRunDep = Annotated[Membership, Depends(live_run_dependency)]
ManageMembersDep = Annotated[Membership, Depends(manage_membership_dependency)]
_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _effective_status(item: LiveProfileAuthorization) -> str:
    if item.status in {"pending", "approved"} and _aware(item.expires_at) <= _now():
        return "expired"
    return item.status


def _public(item: LiveProfileAuthorization) -> ProfileAuthorizationPublic:
    values = {
        "id": item.id,
        "organization_id": item.organization_id,
        "user_id": item.user_id,
        "profile_kind": item.profile_kind,
        "profile_id": item.profile_id,
        "evidence_reference": item.evidence_reference,
        "evidence_sha256": item.evidence_sha256,
        "expires_at": item.expires_at,
        "status": _effective_status(item),
        "requested_by_user_id": item.requested_by_user_id,
        "reviewed_by_user_id": item.reviewed_by_user_id,
        "reviewed_at": item.reviewed_at,
        "revoked_by_user_id": item.revoked_by_user_id,
        "revoked_at": item.revoked_at,
        "created_at": item.created_at,
    }
    return ProfileAuthorizationPublic.model_validate(values)


@page_router.get("/liveshell/profiles", include_in_schema=False)
def liveshell_profiles_page() -> FileResponse:
    return FileResponse(
        WEB_ROOT / "liveshell-profiles.html",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/organizations/{organization_id}/liveshift/profile-authorizations",
    response_model=list[ProfileAuthorizationPublic],
)
def list_profile_authorizations(
    organization_id: UUID,
    membership: LiveRunDep,
    session: SessionDep,
) -> list[ProfileAuthorizationPublic]:
    statement = select(LiveProfileAuthorization).where(
        LiveProfileAuthorization.organization_id == organization_id,
    )
    if not has_permission(membership.role, Permission.MEMBERS_MANAGE):
        statement = statement.where(
            LiveProfileAuthorization.user_id == membership.user_id,
        )
    rows = list(
        session.scalars(
            statement.order_by(
                LiveProfileAuthorization.created_at.desc(),
                LiveProfileAuthorization.id.desc(),
            )
        )
    )
    return [_public(row) for row in rows]


@router.post(
    "/organizations/{organization_id}/liveshift/profile-authorizations",
    response_model=ProfileAuthorizationPublic,
    status_code=status.HTTP_201_CREATED,
)
def request_profile_authorization(
    organization_id: UUID,
    payload: ProfileAuthorizationRequest,
    membership: LiveRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ProfileAuthorizationPublic:
    expires_at = _aware(payload.expires_at)
    now = _now()
    if expires_at <= now or expires_at > now + timedelta(days=365):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="authorization expiry must be within the next 365 days",
        )

    existing = session.scalar(
        select(LiveProfileAuthorization).where(
            LiveProfileAuthorization.organization_id == organization_id,
            LiveProfileAuthorization.user_id == membership.user_id,
            LiveProfileAuthorization.profile_kind == payload.profile_kind,
            LiveProfileAuthorization.profile_id == payload.profile_id,
            LiveProfileAuthorization.status.in_(("pending", "approved")),
        )
    )
    if existing is not None:
        if _effective_status(existing) != "expired":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="an active or pending authorization already exists for this profile",
            )
        existing.status = "expired"
        session.flush()

    item = LiveProfileAuthorization(
        organization_id=organization_id,
        user_id=membership.user_id,
        profile_kind=payload.profile_kind,
        profile_id=payload.profile_id,
        evidence_reference=payload.evidence_reference,
        evidence_sha256=payload.evidence_sha256,
        expires_at=expires_at,
        status="pending",
        requested_by_user_id=current_user.id,
    )
    session.add(item)
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="liveshell.profile_authorization.requested",
        resource_type="live_profile_authorization",
        resource_id=str(item.id),
        details={
            "profile_kind": item.profile_kind,
            "profile_id": item.profile_id,
            "evidence_sha256": item.evidence_sha256,
        },
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an active or pending authorization already exists for this profile",
        ) from exc
    session.refresh(item)
    return _public(item)


@router.post(
    "/organizations/{organization_id}/liveshift/profile-authorizations/{authorization_id}/review",
    response_model=ProfileAuthorizationPublic,
)
def review_profile_authorization(
    organization_id: UUID,
    authorization_id: UUID,
    payload: ProfileAuthorizationReview,
    membership: ManageMembersDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ProfileAuthorizationPublic:
    item = session.scalar(
        select(LiveProfileAuthorization).where(
            LiveProfileAuthorization.organization_id == organization_id,
            LiveProfileAuthorization.id == authorization_id,
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="profile request not found",
        )
    if item.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only pending profile requests can be reviewed",
        )
    if _aware(item.expires_at) <= _now():
        item.status = "expired"
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="profile authorization request has expired",
        )
    if payload.decision == "approve" and current_user.id == item.requested_by_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="the requester cannot approve their own profile authorization",
        )

    item.status = "approved" if payload.decision == "approve" else "rejected"
    item.reviewed_by_user_id = current_user.id
    item.reviewed_at = _now()
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action=f"liveshell.profile_authorization.{item.status}",
        resource_type="live_profile_authorization",
        resource_id=str(item.id),
        details={
            "profile_kind": item.profile_kind,
            "profile_id": item.profile_id,
            "evidence_sha256": item.evidence_sha256,
            "evidence_reviewed": payload.evidence_reviewed,
            "subject_consent_verified": payload.subject_consent_verified,
        },
    )
    session.commit()
    session.refresh(item)
    return _public(item)


@router.delete(
    "/organizations/{organization_id}/liveshift/profile-authorizations/{authorization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_profile_authorization(
    organization_id: UUID,
    authorization_id: UUID,
    membership: LiveRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Response:
    item = session.scalar(
        select(LiveProfileAuthorization).where(
            LiveProfileAuthorization.organization_id == organization_id,
            LiveProfileAuthorization.id == authorization_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile request not found")
    if (
        item.user_id != current_user.id
        and not has_permission(membership.role, Permission.MEMBERS_MANAGE)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the authorized user or an organization manager can revoke this grant",
        )
    if item.status not in {"pending", "approved"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only pending or approved profile grants can be revoked",
        )
    item.status = "revoked"
    item.revoked_at = _now()
    item.revoked_by_user_id = current_user.id
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="liveshell.profile_authorization.revoked",
        resource_type="live_profile_authorization",
        resource_id=str(item.id),
        details={"profile_kind": item.profile_kind, "profile_id": item.profile_id},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _service_token_valid(header: str | None) -> bool:
    expected = settings.live_profile_authorizer_token
    if expected is None or len(expected.encode("utf-8")) < 32:
        return False
    scheme, separator, supplied = (header or "").partition(" ")
    return (
        separator == " "
        and scheme.lower() == "bearer"
        and hmac.compare_digest(supplied, expected)
    )


@internal_router.post(
    "/internal/live-media/profile-authorization-check",
    response_model=ProfileAuthorizationCheckResult,
)
def check_profile_authorizations(
    payload: ProfileAuthorizationCheck,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> ProfileAuthorizationCheckResult:
    expected = settings.live_profile_authorizer_token
    if expected is None or len(expected.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="profile authorization service is not configured",
        )
    if not _service_token_valid(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid profile authorization service credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    rows = list(
        session.scalars(
            select(LiveProfileAuthorization).where(
                LiveProfileAuthorization.organization_id == payload.organization_id,
                LiveProfileAuthorization.user_id == payload.user_id,
                LiveProfileAuthorization.profile_kind.in_(("face", "voice")),
                LiveProfileAuthorization.profile_id.in_(
                    (payload.face_profile_id, payload.voice_profile_id)
                ),
                LiveProfileAuthorization.status == "approved",
            )
        )
    )
    grants = {
        (row.profile_kind, row.profile_id)
        for row in rows
        if _effective_status(row) == "approved"
    }
    return ProfileAuthorizationCheckResult(
        face_profile_authorized=("face", payload.face_profile_id) in grants,
        voice_profile_authorized=("voice", payload.voice_profile_id) in grants,
    )
