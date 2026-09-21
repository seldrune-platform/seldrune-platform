from __future__ import annotations

import logging
import signal
from threading import Event

from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.governance_policy import GovernancePolicy
from backend.app.models.membership import Membership
from backend.app.services.life_cycle import run_life_tick

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
    logger.info("Seldrune life worker started")
    while not stop_event.is_set():
        try:
            result = run_worker_cycle()
            logger.info("life worker cycle: %s", result)
        except Exception:
            logger.exception("life worker cycle failed")
        stop_event.wait(settings.life_worker_interval_seconds)
    logger.info("Seldrune life worker stopped")


if __name__ == "__main__":
    main()
