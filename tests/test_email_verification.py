from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app import models  # noqa: F401
from backend.app.core.security import hash_password
from backend.app.db.base import Base
from backend.app.models.email_verification_token import EmailVerificationToken
from backend.app.models.user import User
from backend.app.services.email_verification import (
    VerificationTokenError,
    consume_email_verification_token,
    issue_email_verification_token,
)


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


def test_verification_token_is_hashed_and_one_time(session: Session) -> None:
    user = _user(session)
    issue = issue_email_verification_token(session, user.id)
    stored = session.scalar(select(EmailVerificationToken))
    assert stored is not None
    assert stored.token_sha256 != issue.token
    assert len(stored.token_sha256) == 64

    verified = consume_email_verification_token(session, issue.token)
    assert verified.id == user.id
    assert verified.email_verified is True
    assert verified.email_verified_at is not None

    with pytest.raises(VerificationTokenError):
        consume_email_verification_token(session, issue.token)


def test_new_issue_invalidates_previous_token(session: Session) -> None:
    user = _user(session)
    first = issue_email_verification_token(session, user.id)
    second = issue_email_verification_token(session, user.id)

    with pytest.raises(VerificationTokenError):
        consume_email_verification_token(session, first.token)
    assert consume_email_verification_token(session, second.token).email_verified is True


def test_expired_verification_token_is_rejected(session: Session) -> None:
    user = _user(session)
    issue = issue_email_verification_token(session, user.id)
    stored = session.scalar(select(EmailVerificationToken))
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()

    with pytest.raises(VerificationTokenError, match="expired"):
        consume_email_verification_token(session, issue.token)
    assert user.email_verified is False
