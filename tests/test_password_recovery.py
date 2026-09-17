from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app import models  # noqa: F401
from backend.app.core.security import hash_password, verify_password
from backend.app.db.base import Base
from backend.app.models.password_reset_token import PasswordResetToken
from backend.app.models.refresh_token import RefreshToken
from backend.app.models.user import User
from backend.app.services.password_recovery import (
    PasswordResetTokenError,
    issue_password_reset_token,
    reset_password_with_token,
)
from backend.app.services.refresh_sessions import issue_refresh_token


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(bind=engine)


def _user(session: Session) -> User:
    user = User(
        email="founder@example.com",
        display_name="Founder",
        password_hash=hash_password("correct horse battery staple"),
    )
    session.add(user)
    session.flush()
    return user


def test_reset_token_is_hashed_one_time_and_changes_password(session: Session) -> None:
    user = _user(session)
    issue = issue_password_reset_token(session, user.id)
    stored = session.scalar(select(PasswordResetToken))
    assert stored is not None
    assert stored.token_sha256 != issue.token
    assert len(stored.token_sha256) == 64

    reset_user = reset_password_with_token(
        session,
        issue.token,
        "new correct horse battery staple",
    )
    assert reset_user.id == user.id
    assert verify_password("new correct horse battery staple", user.password_hash)
    assert not verify_password("correct horse battery staple", user.password_hash)

    with pytest.raises(PasswordResetTokenError):
        reset_password_with_token(
            session,
            issue.token,
            "another correct horse battery staple",
        )


def test_new_issue_invalidates_previous_reset_token(session: Session) -> None:
    user = _user(session)
    first = issue_password_reset_token(session, user.id)
    second = issue_password_reset_token(session, user.id)

    with pytest.raises(PasswordResetTokenError):
        reset_password_with_token(session, first.token, "replacement password 123")
    reset_password_with_token(session, second.token, "replacement password 123")
    assert verify_password("replacement password 123", user.password_hash)


def test_expired_reset_token_is_rejected(session: Session) -> None:
    user = _user(session)
    issue = issue_password_reset_token(session, user.id)
    stored = session.scalar(select(PasswordResetToken))
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()

    with pytest.raises(PasswordResetTokenError):
        reset_password_with_token(session, issue.token, "replacement password 123")
    assert verify_password("correct horse battery staple", user.password_hash)


def test_successful_reset_revokes_all_refresh_sessions(session: Session) -> None:
    user = _user(session)
    first = issue_refresh_token(session, user.id)
    second = issue_refresh_token(session, user.id)
    issue = issue_password_reset_token(session, user.id)

    reset_password_with_token(session, issue.token, "replacement password 123")
    tokens = list(
        session.scalars(
            select(RefreshToken)
            .where(RefreshToken.user_id == user.id)
            .order_by(RefreshToken.created_at)
        )
    )
    assert len(tokens) == 2
    assert all(token.revoked_at is not None for token in tokens)
    assert first.token not in {token.token_sha256 for token in tokens}
    assert second.token not in {token.token_sha256 for token in tokens}
