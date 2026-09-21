from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.life_worker_heartbeat import LifeWorkerHeartbeat


def record_worker_heartbeat(
    session: Session,
    *,
    worker_id: str,
    status: str,
    cycle_count: int,
    commands_advanced: int,
    organization_id: UUID | None = None,
    last_error: str | None = None,
) -> LifeWorkerHeartbeat:
    heartbeat = session.get(LifeWorkerHeartbeat, worker_id)
    now = datetime.now(UTC)
    if heartbeat is None:
        heartbeat = LifeWorkerHeartbeat(worker_id=worker_id)
        session.add(heartbeat)
    heartbeat.organization_id = organization_id
    heartbeat.status = status
    heartbeat.cycle_count = cycle_count
    heartbeat.commands_advanced = commands_advanced
    heartbeat.last_error = last_error
    heartbeat.last_seen_at = now
    session.commit()
    return heartbeat
