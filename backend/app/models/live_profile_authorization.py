from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base

_ACTIVE_STATUSES = "status IN ('pending', 'approved')"


class LiveProfileAuthorization(Base):
    """Human-reviewed grant for one face or voice profile in one organization."""

    __tablename__ = "live_profile_authorizations"
    __table_args__ = (
        CheckConstraint(
            "profile_kind IN ('face', 'voice')",
            name="ck_live_profile_authorizations_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'revoked', 'expired')",
            name="ck_live_profile_authorizations_status",
        ),
        Index(
            "uq_live_profile_authorizations_active",
            "organization_id",
            "user_id",
            "profile_kind",
            "profile_id",
            unique=True,
            sqlite_where=text(_ACTIVE_STATUSES),
            postgresql_where=text(_ACTIVE_STATUSES),
        ),
        Index(
            "ix_live_profile_authorizations_org_user",
            "organization_id",
            "user_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
