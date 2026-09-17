from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import SessionDep
from backend.app.schemas.auth import EmailVerificationRequest, EmailVerificationResponse
from backend.app.services.audit import record_audit
from backend.app.services.email_verification import (
    VerificationTokenError,
    consume_email_verification_token,
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
