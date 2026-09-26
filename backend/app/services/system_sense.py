from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models.agent import Agent
from backend.app.models.life_worker_heartbeat import LifeWorkerHeartbeat
from backend.app.models.security_event import SecurityEvent
from backend.app.models.task import Task
from backend.app.services.model_provider_registry import (
    configured_model_provider_vaults,
    model_provider_statuses,
)


_TERMINAL_TASK_STATUSES = {"completed", "succeeded", "failed", "cancelled", "canceled"}
_ATTENTION_SEVERITIES = {"high", "critical"}


def _as_utc(value: datetime, now: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=now.tzinfo)
    return value.astimezone(now.tzinfo)


def build_system_sense_snapshot(
    session: Session,
    *,
    organization_id: UUID,
    settings: Settings,
    now: datetime | None = None,
) -> dict:
    sampled_at = now or datetime.now(UTC)
    agent_total = int(
        session.scalar(
            select(func.count(Agent.id)).where(
                Agent.organization_id == organization_id
            )
        )
        or 0
    )
    agent_active = int(
        session.scalar(
            select(func.count(Agent.id)).where(
                Agent.organization_id == organization_id,
                Agent.status == "active",
            )
        )
        or 0
    )
    task_statuses = {
        str(task_status): int(count)
        for task_status, count in session.execute(
            select(Task.status, func.count(Task.id))
            .where(Task.organization_id == organization_id)
            .group_by(Task.status)
        )
    }
    open_tasks = sum(
        count
        for task_status, count in task_statuses.items()
        if task_status.casefold() not in _TERMINAL_TASK_STATUSES
    )
    failed_tasks = sum(
        count
        for task_status, count in task_statuses.items()
        if task_status.casefold() in {"failed", "error"}
    )
    open_security = {
        str(severity): int(count)
        for severity, count in session.execute(
            select(SecurityEvent.severity, func.count(SecurityEvent.id))
            .where(
                SecurityEvent.organization_id == organization_id,
                SecurityEvent.status == "open",
            )
            .group_by(SecurityEvent.severity)
        )
    }
    heartbeat = session.scalars(
        select(LifeWorkerHeartbeat).order_by(
            LifeWorkerHeartbeat.last_seen_at.desc()
        )
    ).first()
    if heartbeat is None:
        worker = {
            "status": "missing",
            "alive": False,
            "last_seen_at": None,
            "age_seconds": None,
            "cycle_count": 0,
            "commands_advanced": 0,
            "sample_interval_seconds": settings.life_worker_interval_seconds,
        }
    else:
        last_seen = _as_utc(heartbeat.last_seen_at, sampled_at)
        age_seconds = max(0, int((sampled_at - last_seen).total_seconds()))
        stale_after = max(60, int(settings.life_worker_interval_seconds * 3))
        worker = {
            "status": heartbeat.status,
            "alive": heartbeat.status == "running" and age_seconds <= stale_after,
            "last_seen_at": last_seen.isoformat(),
            "age_seconds": age_seconds,
            "cycle_count": heartbeat.cycle_count,
            "commands_advanced": heartbeat.commands_advanced,
            "sample_interval_seconds": settings.life_worker_interval_seconds,
        }

    critical_security = any(
        severity.casefold() in _ATTENTION_SEVERITIES and count > 0
        for severity, count in open_security.items()
    )
    if worker["status"] == "missing":
        health = "unknown"
    elif not worker["alive"] or critical_security or failed_tasks:
        health = "attention"
    else:
        health = "healthy"

    return {
        "organization_id": str(organization_id),
        "sampled_at": sampled_at.isoformat(),
        "system": {
            "health": health,
            "continuous_sampling_active": bool(worker["alive"]),
            "monitored_signals": [
                "agents",
                "task_status",
                "open_security_events",
                "life_worker_heartbeat",
                "model_provider_configuration",
            ],
        },
        "agents": {"total": agent_total, "active": agent_active},
        "tasks": {
            "total": sum(task_statuses.values()),
            "open": open_tasks,
            "failed": failed_tasks,
            "by_status": task_statuses,
        },
        "security_events": {
            "open": sum(open_security.values()),
            "by_severity": open_security,
        },
        "life_worker": worker,
        "model_providers": model_provider_statuses(
            settings,
            vault_configured=configured_model_provider_vaults(
                session,
                organization_id=organization_id,
            ),
        ),
    }
