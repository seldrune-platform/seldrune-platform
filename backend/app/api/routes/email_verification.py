from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import SessionDep
from backend.app.models.user import User
from backend.app.schemas.auth import (
    EmailVerificationRequest,
    EmailVerificationResponse,
    ResendVerificationRequest,
)
from backend.app.services.audit import record_audit
from backend.app.services.email_delivery import EmailDeliveryError, send_verification_email
from backend.app.services.email_verification import (
    VerificationTokenError,
    consume_email_verification_token,
    issue_email_verification_token,
)
from backend.app.services.security_events import record_user_security_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/verify-email", response_model=EmailVerificationResponse)
def verify_email(
    payload: EmailVerificationRequest,
    session: SessionDep,
) -> EmailVerificationResponse:
    try:
        user = consume_email_verification_token(session, payload.token)
    except VerificationTokenError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        ) from exc

    record_audit(
        session,
        action="auth.email_verified",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=str(user.id),
    )
    record_user_security_event(
        session,
        user_id=user.id,
        event_type="email_verified",
        severity="low",
        resource_type="user",
        resource_id=str(user.id),
    )
    session.commit()
    return EmailVerificationResponse(verified=True)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(
    payload: ResendVerificationRequest,
    session: SessionDep,
) -> dict[str, str]:
    # Deliberately return the same response for unknown/already-verified emails
    # to avoid account enumeration.
    email = str(payload.email).strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or user.email_verified:
        return {"status": "accepted"}

    issue = issue_email_verification_token(session, user.id)
    session.commit()
    try:
        send_verification_email(user.email, issue.token)
    except EmailDeliveryError:
        # Keep the public response non-enumerating; operators can diagnose SMTP
        # health independently without exposing account state or token data.
        pass
    return {"status": "accepted"}
