from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class LifeWorkerHeartbeat(Base):
    __tablename__ = "life_worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    organization_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="starting")
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    commands_advanced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
