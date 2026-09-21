from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.life_lease import LifeLease


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def acquire_life_lease(
    session: Session,
    *,
    orchestration_run_id: UUID,
    organization_id: UUID,
    worker_id: str,
    ttl_seconds: int = 120,
) -> bool:
    """Atomically claim a run, or take over an expired lease."""
    now = utcnow()
    expires = now + timedelta(seconds=max(ttl_seconds, 1))
    takeover = session.execute(
        update(LifeLease)
        .where(
            LifeLease.orchestration_run_id == orchestration_run_id,
            LifeLease.lease_expires_at <= now,
        )
        .values(
            organization_id=organization_id,
            worker_id=worker_id,
            lease_expires_at=expires,
            acquired_at=now,
            renewed_at=now,
        )
    )
    if takeover.rowcount:
        session.commit()
        return True

    session.add(
        LifeLease(
            orchestration_run_id=orchestration_run_id,
            organization_id=organization_id,
            worker_id=worker_id,
            lease_expires_at=expires,
            acquired_at=now,
            renewed_at=now,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return False
    return True


def renew_life_lease(
    session: Session,
    *,
    orchestration_run_id: UUID,
    worker_id: str,
    ttl_seconds: int = 120,
) -> bool:
    now = utcnow()
    renewed = session.execute(
        update(LifeLease)
        .where(
            LifeLease.orchestration_run_id == orchestration_run_id,
            LifeLease.worker_id == worker_id,
            LifeLease.lease_expires_at > now,
        )
        .values(
            lease_expires_at=now + timedelta(seconds=max(ttl_seconds, 1)),
            renewed_at=now,
        )
    )
    session.commit()
    return bool(renewed.rowcount)


def release_life_lease(
    session: Session,
    *,
    orchestration_run_id: UUID,
    worker_id: str,
) -> bool:
    released = session.execute(
        delete(LifeLease).where(
            LifeLease.orchestration_run_id == orchestration_run_id,
            LifeLease.worker_id == worker_id,
        )
    )
    session.commit()
    return bool(released.rowcount)
