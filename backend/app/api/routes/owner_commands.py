from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _get_run, _to_public
from backend.app.core.orchestration import build_default_plan
from backend.app.core.rbac import Permission, Role
from backend.app.models.membership import Membership
from backend.app.models.orchestration import OrchestrationRun
from backend.app.schemas.orchestration import (
    AutonomousExecutionRequest,
    AutonomousExecutionResponse,
    OrchestrationCreate,
    OrchestrationRunPublic,
)
from backend.app.services.audit import record_audit
from backend.app.services.autonomous_execution import execute_orchestration_autonomously
from backend.app.services.orchestrator import create_orchestration_run, refresh_orchestration_status
from backend.app.services.owner_dashboard import build_decision_brief, build_owner_dashboard

router = APIRouter(prefix="/organizations", tags=["owner-command-center"])
OwnerDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_MANAGE))]


def _require_owner(membership: Membership) -> None:
    if membership.role != Role.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")


def _is_owner_command(run: OrchestrationRun) -> bool:
    return bool((run.context or {}).get("owner_command"))


@router.post(
    "/{organization_id}/owner-commands",
    response_model=OrchestrationRunPublic,
    status_code=201,
)
def create_owner_command(
    organization_id: UUID,
    payload: OrchestrationCreate,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrchestrationRunPublic:
    _require_owner(membership)
    context = {
        **payload.context,
        "owner_command": {"approval_status": "awaiting_approval", "approved_by": None},
    }
    run = create_orchestration_run(
        session,
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        objective=payload.objective,
        context=context,
        plan=build_default_plan(payload.objective),
    )
    record_audit(session, organization_id=organization_id, actor_user_id=current_user.id,
                 action="owner_command.created", resource_type="orchestration",
                 resource_id=str(run.id), details={"approval_status": "awaiting_approval"})
    session.commit()
    session.refresh(run)
    return _to_public(session, run)


@router.get("/{organization_id}/owner-commands", response_model=list[OrchestrationRunPublic])
def list_owner_commands(
    organization_id: UUID, membership: OwnerDep, session: SessionDep
) -> list[OrchestrationRunPublic]:
    _require_owner(membership)
    runs = list(session.scalars(select(OrchestrationRun).where(
        OrchestrationRun.organization_id == organization_id
    ).order_by(OrchestrationRun.created_at.desc())))
    commands = [run for run in runs if _is_owner_command(run)]
    for run in commands:
        refresh_orchestration_status(session, run)
    session.commit()
    return [_to_public(session, run) for run in commands]


@router.get("/{organization_id}/owner-dashboard", response_model=dict[str, Any])
def get_owner_dashboard(
    organization_id: UUID, membership: OwnerDep, session: SessionDep
) -> dict[str, Any]:
    _require_owner(membership)
    return build_owner_dashboard(session, organization_id)


@router.get(
    "/{organization_id}/owner-commands/{run_id}/brief",
    response_model=dict[str, Any],
)
def get_owner_command_brief(
    organization_id: UUID, run_id: UUID, membership: OwnerDep, session: SessionDep
) -> dict[str, Any]:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    if not _is_owner_command(run):
        raise HTTPException(status_code=404, detail="Owner command not found")
    refresh_orchestration_status(session, run)
    session.commit()
    return build_decision_brief(session, run)


@router.post(
    "/{organization_id}/owner-commands/{run_id}/approve",
    response_model=OrchestrationRunPublic,
)
def approve_owner_command(
    organization_id: UUID, run_id: UUID, membership: OwnerDep,
    current_user: CurrentUserDep, session: SessionDep,
) -> OrchestrationRunPublic:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    if not _is_owner_command(run):
        raise HTTPException(status_code=404, detail="Owner command not found")
    run.context = {**run.context, "owner_command": {
        **run.context["owner_command"], "approval_status": "approved",
        "approved_by": str(current_user.id),
    }}
    record_audit(session, organization_id=organization_id, actor_user_id=current_user.id,
                 action="owner_command.approved", resource_type="orchestration",
                 resource_id=str(run.id), details={})
    session.commit()
    session.refresh(run)
    return _to_public(session, run)


@router.post(
    "/{organization_id}/owner-commands/{run_id}/execute",
    response_model=AutonomousExecutionResponse,
)
def execute_owner_command(
    organization_id: UUID, run_id: UUID, payload: AutonomousExecutionRequest,
    membership: OwnerDep, current_user: CurrentUserDep, session: SessionDep,
) -> AutonomousExecutionResponse:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    command = (run.context or {}).get("owner_command")
    if not command:
        raise HTTPException(status_code=404, detail="Owner command not found")
    if command.get("approval_status") != "approved":
        raise HTTPException(status_code=409, detail="Owner command requires approval")
    report = execute_orchestration_autonomously(
        session, run=run, actor_user_id=current_user.id,
        stop_on_failure=payload.stop_on_failure, max_steps=payload.max_steps,
        max_retries_per_step=payload.max_retries_per_step,
        max_upstream_text_chars=payload.max_upstream_text_chars,
    )
    return AutonomousExecutionResponse(run=_to_public(session, run), execution=report)
