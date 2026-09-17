from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.email_verification_token import EmailVerificationToken
from backend.app.models.user import User


DEFAULT_VERIFICATION_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class VerificationIssue:
    token: str
    expires_at: datetime


class VerificationTokenError(ValueError):
    """Raised when an email verification token is invalid or unusable."""


def _digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def issue_email_verification_token(
    session: Session,
    user_id: UUID,
    *,
    ttl: timedelta = DEFAULT_VERIFICATION_TTL,
) -> VerificationIssue:
    now = datetime.now(UTC)
    expires_at = now + ttl
    token = secrets.token_urlsafe(48)

    session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    session.add(
        EmailVerificationToken(
            user_id=user_id,
            token_sha256=_digest(token),
            expires_at=expires_at,
        )
    )
    session.flush()
    return VerificationIssue(token=token, expires_at=expires_at)


def consume_email_verification_token(session: Session, token: str) -> User:
    now = datetime.now(UTC)
    record = session.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_sha256 == _digest(token)
        )
    )
    if record is None or record.consumed_at is not None:
        raise VerificationTokenError("Invalid or already used verification token")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        record.consumed_at = now
        session.flush()
        raise VerificationTokenError("Verification token has expired")

    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        raise VerificationTokenError("Verification account is unavailable")

    record.consumed_at = now
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = now
    session.flush()
    return user
