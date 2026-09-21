from __future__ import annotations

import logging
import signal
from uuid import uuid4
from threading import Event

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.governance_policy import GovernancePolicy
from backend.app.models.membership import Membership
from backend.app.services.life_cycle import run_life_tick
from backend.app.services.life_heartbeat import record_worker_heartbeat

logger = logging.getLogger("seldrune.life_worker")
stop_event = Event()


def _request_stop(*_: object) -> None:
    stop_event.set()


def run_worker_cycle() -> dict[str, int]:
    organizations = 0
    advanced = 0
    with SessionLocal() as session:
        policies = list(
            session.scalars(
                select(GovernancePolicy).where(
                    GovernancePolicy.allow_autonomous_execution.is_(True)
                )
            )
        )
        for policy in policies:
            owner_id = session.scalar(
                select(Membership.user_id)
                .where(
                    Membership.organization_id == policy.organization_id,
                    Membership.role == "owner",
                )
                .limit(1)
            )
            if owner_id is None:
                continue
            organizations += 1
            result = run_life_tick(
                session,
                organization_id=policy.organization_id,
                actor_user_id=owner_id,
                max_commands=settings.life_worker_max_commands,
                max_steps_per_command=settings.life_worker_max_steps_per_command,
                max_retries_per_step=settings.life_worker_max_retries_per_step,
            )
            advanced += int(result["commands_advanced"])
    return {"organizations": organizations, "commands_advanced": advanced}


def main() -> None:
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    worker_id = f"life-worker:{uuid4()}"
    cycle_count = 0
    commands_advanced = 0
    with SessionLocal() as session:
        record_worker_heartbeat(\n            session,\n            worker_id=worker_id,\n            status="starting",\n            cycle_count=0,\n            commands_advanced=0,\n        )
    logger.info("Seldrune life worker started: %s", worker_id)
    while not stop_event.is_set():
        try:
            result = run_worker_cycle()
            cycle_count += 1
            commands_advanced += result["commands_advanced"]
            with SessionLocal() as session:
                record_worker_heartbeat(\n                    session,\n                    worker_id=worker_id,\n                    status="running",\n                    cycle_count=cycle_count,\n                    commands_advanced=commands_advanced,\n                )
            logger.info("life worker cycle: %s", result)
        except Exception as exc:
            with SessionLocal() as session:
                record_worker_heartbeat(\n                    session,\n                    worker_id=worker_id,\n                    status="error",\n                    cycle_count=cycle_count,\n                    commands_advanced=commands_advanced,\n                    last_error=str(exc)[:2000],\n                )
            logger.exception("life worker cycle failed")
        stop_event.wait(settings.life_worker_interval_seconds)
    with SessionLocal() as session:
        record_worker_heartbeat(\n            session,\n            worker_id=worker_id,\n            status="stopped",\n            cycle_count=cycle_count,\n            commands_advanced=commands_advanced,\n        )
    logger.info("Seldrune life worker stopped")


if __name__ == "__main__":
    main()
