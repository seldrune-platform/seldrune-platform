from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.governance_policy import GovernancePolicy
from backend.app.models.orchestration import OrchestrationRun
from backend.app.services.audit import record_audit
from backend.app.services.autonomous_execution import execute_orchestration_autonomously
from backend.app.services.orchestrator import refresh_orchestration_status


_TERMINAL = {"completed", "failed", "cancelled"}


def _approved_owner_command(run: OrchestrationRun) -> bool:
    owner_command = (run.context or {}).get("owner_command") or {}
    return owner_command.get("approval_status") == "approved"


def run_life_tick(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    max_commands: int = 5,
    max_steps_per_command: int | None = None,
    max_retries_per_step: int = 1,
) -> dict[str, Any]:
    """Advance a bounded set of approved owner commands from durable state."""
    policy = session.get(GovernancePolicy, organization_id)
    if policy is None or not policy.allow_autonomous_execution:
        return {
            "mode": "life-tick-v1",
            "status": "governance_blocked",
            "commands_considered": 0,
            "commands_advanced": 0,
            "reports": [],
        }

    requested_step_limit = max_steps_per_command or policy.max_steps_per_command
    step_limit = min(requested_step_limit, policy.max_steps_per_command)
    candidates = list(
        session.scalars(
            select(OrchestrationRun)
            .where(OrchestrationRun.organization_id == organization_id)
            .order_by(OrchestrationRun.updated_at.asc())
            .limit(max(max_commands * 4, max_commands))
        )
    )
    eligible = [
        run
        for run in candidates
        if run.status not in _TERMINAL and _approved_owner_command(run)
    ][:max_commands]

    reports: list[dict[str, Any]] = []
    for run in eligible:
        before = run.status
        execution = execute_orchestration_autonomously(
            session,
            run=run,
            actor_user_id=actor_user_id,
            stop_on_failure=True,
            max_steps=step_limit,
            max_retries_per_step=max_retries_per_step,
        )
        refresh_orchestration_status(session, run)
        report = {
            "run_id": str(run.id),
            "objective": run.objective,
            "before_status": before,
            "after_status": run.status,
            "execution": execution,
        }
        reports.append(report)
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="seldrune.life.tick",
            resource_type="orchestration",
            resource_id=str(run.id),
            details=report,
        )
        session.commit()

    return {
        "mode": "life-tick-v1",
        "status": "advanced" if reports else "idle",
        "commands_considered": len(eligible),
        "commands_advanced": len(reports),
        "max_commands": max_commands,
        "max_steps_per_command": step_limit,
        "max_retries_per_step": max_retries_per_step,
        "reports": reports,
    }
