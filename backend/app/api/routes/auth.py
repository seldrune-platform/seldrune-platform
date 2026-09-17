from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.app.api.dependencies import CurrentUserDep, SessionDep, TokenDep
from backend.app.core.config import settings
from backend.app.core.mfa import derive_totp_secret, verify_totp
from backend.app.core.rbac import ROLE_PERMISSIONS, Role
from backend.app.core.security import (
    TokenError,
    access_token_fingerprint,
    create_access_token,
    decode_access_token_claims,
    hash_password,
    verify_password,
)
from backend.app.models.membership import Membership
from backend.app.models.organization import Organization
from backend.app.models.revoked_access_token import RevokedAccessToken
from backend.app.models.user import User
from backend.app.schemas.auth import (
    AuthResponse,
    BootstrapStatus,
    LoginRequest,
    MeResponse,
    PasswordRecoveryRequest,
    PasswordResetRequest,
    MembershipPublic,
    OrganizationPublic,
    RefreshRequest,
    RegisterRequest,
    UserPublic,
)
from backend.app.services.audit import record_audit
from backend.app.services.email_delivery import (
    EmailDeliveryError,
    send_password_reset_email,
    send_verification_email,
)
from backend.app.services.email_verification import issue_email_verification_token
from backend.app.services.login_throttle import (
    LoginThrottleError,
    clear_login_failures,
    enforce_login_throttle,
    login_throttle_key,
    record_login_failure,
)
from backend.app.services.mfa_recovery import consume_recovery_code
from backend.app.services.password_recovery import (
    PasswordResetTokenError,
    issue_password_reset_token,
    reset_password_with_token,
)
from backend.app.services.refresh_sessions import (
    RefreshIssue,
    RefreshTokenError,
    RefreshTokenReplay,
    issue_refresh_token,
    revoke_refresh_family,
    rotate_refresh_token,
)
from backend.app.services.security_events import record_user_security_event

router = APIRouter(prefix="/auth", tags=["auth"])
_BOOTSTRAP_LOCK_ID = 7_341_337_006_011


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _auth_response(
    session: SessionDep,
    user: User,
    refresh_issue: RefreshIssue | None = None,
) -> AuthResponse:
    issue = refresh_issue or issue_refresh_token(session, user.id)
    refresh_expires_in = max(
        0,
        int((_aware(issue.expires_at) - datetime.now(UTC)).total_seconds()),
    )
    return AuthResponse(
        access_token=create_access_token(user.id, session_id=issue.family_id),
        refresh_token=issue.token,
        expires_in=settings.auth_access_token_minutes * 60,
        refresh_expires_in=refresh_expires_in,
        user=UserPublic.model_validate(user),
    )


def _bootstrap_required(session: SessionDep) -> bool:
    return session.scalar(select(Organization.id).limit(1)) is None


def _raise_login_throttled(exc: LoginThrottleError) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=str(exc),
        headers={"Retry-After": str(exc.retry_after_seconds)},
    ) from exc


def _reject_login(session: SessionDep, throttle_key: str) -> None:
    try:
        record_login_failure(session, throttle_key)
    except LoginThrottleError as exc:
        _raise_login_throttled(exc)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _refresh_credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/bootstrap-status", response_model=BootstrapStatus)
def bootstrap_status(session: SessionDep) -> BootstrapStatus:
    return BootstrapStatus(required=_bootstrap_required(session))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: SessionDep) -> AuthResponse:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": _BOOTSTRAP_LOCK_ID},
        )

    if not _bootstrap_required(session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner onboarding is already complete",
        )

    email = str(payload.email).strip().lower()
    slug = payload.organization_slug.strip().lower()

    if session.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if session.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        )

    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )
    organization = Organization(name=payload.organization_name.strip(), slug=slug)
    session.add_all([user, organization])

    try:
        session.flush()
        membership = Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=Role.OWNER.value,
        )
        session.add(membership)
        record_audit(
            session,
            action="auth.register",
            resource_type="user",
            organization_id=organization.id,
            actor_user_id=user.id,
            resource_id=str(user.id),
        )
        verification_issue = issue_email_verification_token(session, user.id)
        response = _auth_response(session, user)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration conflicts with an existing account",
        ) from exc

    try:
        send_verification_email(user.email, verification_issue.token)
    except EmailDeliveryError:
        # Registration must remain usable during provider outages; the owner can
        # request a fresh verification message once delivery is restored.
        pass
    return response


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: PasswordRecoveryRequest,
    session: SessionDep,
) -> dict[str, str]:
    email = str(payload.email).strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return {"status": "accepted"}

    issue = issue_password_reset_token(session, user.id)
    record_audit(
        session,
        action="auth.password_reset_requested",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=str(user.id),
    )
    record_user_security_event(
        session,
        user_id=user.id,
        event_type="password_reset_requested",
        severity="low",
        resource_type="user",
        resource_id=str(user.id),
    )
    session.commit()

    try:
        send_password_reset_email(user.email, issue.token)
    except EmailDeliveryError:
        pass
    return {"status": "accepted"}


@router.post("/reset-password")
def reset_password(
    payload: PasswordResetRequest,
    session: SessionDep,
) -> dict[str, str]:
    try:
        user = reset_password_with_token(session, payload.token, payload.new_password)
    except PasswordResetTokenError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        ) from exc

    record_audit(
        session,
        action="auth.password_reset",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=str(user.id),
    )
    record_user_security_event(
        session,
        user_id=user.id,
        event_type="password_reset",
        severity="medium",
        resource_type="user",
        resource_id=str(user.id),
    )
    session.commit()
    return {"status": "reset"}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, session: SessionDep) -> AuthResponse:
    email = str(payload.email).strip().lower()
    source_address = request.client.host if request.client is not None else "unknown"
    throttle_key = login_throttle_key(email, source_address)

    try:
        enforce_login_throttle(session, throttle_key)
    except LoginThrottleError as exc:
        _raise_login_throttled(exc)

    user = session.scalar(select(User).where(User.email == email))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        _reject_login(session, throttle_key)

    mfa_factor: str | None = None
    if user.mfa_enabled:
        if payload.mfa_code is not None:
            if not user.mfa_nonce:
                _reject_login(session, throttle_key)
            secret = derive_totp_secret(user.id, user.mfa_nonce)
            if not verify_totp(secret, payload.mfa_code):
                _reject_login(session, throttle_key)
            mfa_factor = "totp"
        elif payload.recovery_code is not None:
            if not consume_recovery_code(session, user.id, payload.recovery_code):
                _reject_login(session, throttle_key)
            mfa_factor = "recovery_code"
        else:
            _reject_login(session, throttle_key)

    clear_login_failures(session, throttle_key)
    if mfa_factor == "recovery_code":
        record_audit(
            session,
            action="auth.mfa_recovery_code_used",
            resource_type="user",
            actor_user_id=user.id,
            resource_id=str(user.id),
        )
        record_user_security_event(
            session,
            user_id=user.id,
            event_type="mfa_recovery_code_used",
            severity="medium",
            resource_type="user",
            resource_id=str(user.id),
        )
    record_audit(
        session,
        action="auth.login",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=str(user.id),
        details={"mfa_factor": mfa_factor} if mfa_factor is not None else {},
    )
    response = _auth_response(session, user)
    session.commit()
    return response


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, session: SessionDep) -> AuthResponse:
    try:
        user_id, replacement = rotate_refresh_token(session, payload.refresh_token)
    except RefreshTokenReplay as exc:
        record_audit(
            session,
            action="auth.refresh_reuse_detected",
            resource_type="user",
            actor_user_id=exc.user_id,
            resource_id=str(exc.user_id),
            details={"family_id": str(exc.family_id)},
        )
        record_user_security_event(
            session,
            user_id=exc.user_id,
            event_type="refresh_token_reuse",
            severity="critical",
            resource_type="user",
            resource_id=str(exc.user_id),
        )
        session.commit()
        raise _refresh_credentials_error() from exc
    except RefreshTokenError as exc:
        session.rollback()
        raise _refresh_credentials_error() from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        revoke_refresh_family(session, replacement.family_id)
        session.commit()
        raise _refresh_credentials_error()

    record_audit(
        session,
        action="auth.refresh_rotated",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=str(user.id),
        details={"family_id": str(replacement.family_id)},
    )
    response = _auth_response(session, user, replacement)
    session.commit()
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: TokenDep, session: SessionDep) -> Response:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token_claims(token)
    except TokenError as exc:
        raise credentials_error from exc

    user = session.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise credentials_error

    fingerprint = access_token_fingerprint(token)
    existing = session.scalar(
        select(RevokedAccessToken.id).where(
            RevokedAccessToken.token_sha256 == fingerprint,
        )
    )
    first_revocation = existing is None
    if first_revocation:
        session.add(
            RevokedAccessToken(
                user_id=user.id,
                token_sha256=fingerprint,
                expires_at=claims.expires_at,
            )
        )
    if claims.session_id is not None:
        revoke_refresh_family(session, claims.session_id)

    if first_revocation:
        record_audit(
            session,
            action="auth.logout",
            resource_type="user",
            actor_user_id=user.id,
            resource_id=str(user.id),
            details=(
                {"family_id": str(claims.session_id)}
                if claims.session_id is not None
                else {}
            ),
        )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUserDep, session: SessionDep) -> MeResponse:
    rows = session.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == current_user.id)
        .order_by(Organization.name)
    ).all()

    memberships = [
        MembershipPublic(
            organization=OrganizationPublic.model_validate(organization),
            role=membership.role,
            permissions=sorted(
                permission.value for permission in ROLE_PERMISSIONS[Role(membership.role)]
            ),
        )
        for membership, organization in rows
    ]
    return MeResponse(
        user=UserPublic.model_validate(current_user),
        memberships=memberships,
    )
