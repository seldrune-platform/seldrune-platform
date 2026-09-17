from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.models.password_reset_token import PasswordResetToken
from backend.app.models.user import User
from backend.app.services.refresh_sessions import revoke_user_refresh_sessions

DEFAULT_PASSWORD_RESET_TTL = timedelta(hours=1)


class PasswordResetTokenError(ValueError):
    """Raised when a password reset token cannot be accepted."""


@dataclass(frozen=True)
class PasswordResetIssue:
    token: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def password_reset_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_password_reset_token(
    session: Session,
    user_id: UUID,
    *,
    ttl: timedelta = DEFAULT_PASSWORD_RESET_TTL,
) -> PasswordResetIssue:
    now = _now()
    raw_token = secrets.token_urlsafe(48)
    expires_at = now + ttl

    session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    session.add(
        PasswordResetToken(
            user_id=user_id,
            token_sha256=password_reset_fingerprint(raw_token),
            expires_at=expires_at,
        )
    )
    session.flush()
    return PasswordResetIssue(token=raw_token, expires_at=expires_at)


def reset_password_with_token(
    session: Session,
    token: str,
    new_password: str,
) -> User:
    statement = select(PasswordResetToken).where(
        PasswordResetToken.token_sha256 == password_reset_fingerprint(token)
    )
    if session.get_bind().dialect.name != "sqlite":
        statement = statement.with_for_update()
    reset_token = session.scalar(statement)
    if reset_token is None or reset_token.consumed_at is not None:
        raise PasswordResetTokenError("Invalid password reset token")

    now = _now()
    if _aware(reset_token.expires_at) <= now:
        reset_token.consumed_at = now
        session.flush()
        raise PasswordResetTokenError("Invalid password reset token")

    user = session.get(User, reset_token.user_id)
    if user is None or not user.is_active:
        reset_token.consumed_at = now
        session.flush()
        raise PasswordResetTokenError("Invalid password reset token")

    user.password_hash = hash_password(new_password)
    reset_token.consumed_at = now
    revoke_user_refresh_sessions(session, user.id)
    session.flush()
    return user
