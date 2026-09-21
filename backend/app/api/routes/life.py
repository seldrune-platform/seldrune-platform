from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _get_run, _to_public
from backend.app.core.rbac import Permission, Role
from backend.app.core.tasking import TaskStatus
from backend.app.models.membership import Membership
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task
from backend.app.schemas.orchestration import AutonomousExecutionRequest
from backend.app.services.audit import record_audit
from backend.app.services.autonomous_execution import execute_orchestration_autonomously
from backend.app.services.orchestrator import refresh_orchestration_status

router = APIRouter(prefix="/organizations", tags=["seldrune-life"])
OwnerDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_MANAGE))]


def _require_owner(membership: Membership) -> None:
    if membership.role != Role.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")


def _owner_command(run: OrchestrationRun) -> bool:
    return bool((run.context or {}).get("owner_command"))


@router.get("/{organization_id}/life/heartbeat", response_model=dict[str, Any])
def life_heartbeat(
    organization_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
) -> dict[str, Any]:
    """Return durable evidence that the governed execution loop has work and state."""
    _require_owner(membership)
    runs = [
        run
        for run in session.scalars(
            select(OrchestrationRun)
            .where(OrchestrationRun.organization_id == organization_id)
            .order_by(OrchestrationRun.updated_at.desc())
            .limit(100)
        )
        if _owner_command(run)
    ]
    for run in runs:
        refresh_orchestration_status(session, run)
    task_counts = dict(
        session.execute(
            select(Task.status, func.count(Task.id))
            .where(Task.organization_id == organization_id)
            .group_by(Task.status)
        ).all()
    )
    session.commit()
    active = sum(
        task_counts.get(state.value, 0)
        for state in (TaskStatus.ASSIGNED, TaskStatus.RUNNING, TaskStatus.QUEUED)
    )
    failed = task_counts.get(TaskStatus.FAILED.value, 0)
    verified = task_counts.get(TaskStatus.SUCCEEDED.value, 0)
    latest = runs[0] if runs else None
    return {
        "alive": True,
        "source": "durable-database-state",
        "observed_at": datetime.now(UTC),
        "loop": {
            "sense": "durable-state-observed",
            "plan": "owner-command-orchestrator",
            "act": "autonomous-execution-engine",
            "verify": "task-status-and-audit-evidence",
        },
        "counts": {
            "owner_commands": len(runs),
            "active_tasks": active,
            "verified_tasks": verified,
            "failed_tasks": failed,
        },
        "latest_command": (
            {
                "id": str(latest.id),
                "objective": latest.objective,
                "status": latest.status,
                "updated_at": latest.updated_at,
            }
            if latest
            else None
        ),
    }


@router.post("/{organization_id}/life/pulse/{run_id}", response_model=dict[str, Any])
def life_pulse(
    organization_id: UUID,
    run_id: UUID,
    payload: AutonomousExecutionRequest,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    """Advance one approved owner command through the existing governed executor."""
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    if not _owner_command(run):
        raise HTTPException(status_code=404, detail="Owner command not found")
    approval = (run.context or {}).get("owner_command", {}).get("approval_status")
    if approval != "approved":
        raise HTTPException(status_code=409, detail="Owner approval required before life pulse")
    before = run.status
    result = execute_orchestration_autonomously(
        session,
        run=run,
        actor_user_id=current_user.id,
        request=payload,
    )
    refresh_orchestration_status(session, run)
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="seldrune.life.pulse",
        resource_type="orchestration",
        resource_id=str(run.id),
        details={
            "before_status": before,
            "after_status": run.status,
            "executed_steps": result.executed_steps,
            "failed_steps": result.failed_steps,
            "halted_reason": result.halted_reason,
        },
    )
    session.commit()
    session.refresh(run)
    return {
        "alive": True,
        "pulse": {
            "before_status": before,
            "after_status": run.status,
            "execution": result.model_dump(mode="json"),
        },
        "run": _to_public(session, run).model_dump(mode="json"),
    }
