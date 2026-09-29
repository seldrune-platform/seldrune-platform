from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class MCPOAuthClient(Base):
    __tablename__ = "mcp_oauth_clients"

    client_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    redirect_uris: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    token_endpoint_auth_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MCPAuthorizationCode(Base):
    __tablename__ = "mcp_oauth_codes"

    code_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(200), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(8), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MCPRefreshToken(Base):
    __tablename__ = "mcp_oauth_refresh_tokens"

    token_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(200), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

