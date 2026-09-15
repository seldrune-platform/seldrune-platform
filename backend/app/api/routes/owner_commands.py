from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _get_run, _to_public
from backend.app.core.rbac import Permission, Role
from backend.app.models.membership import Membership
from backend.app.models.organization_kernel import OrganizationProject
from backend.app.models.orchestration import OrchestrationRun
from backend.app.schemas.orchestration import (
    AutonomousExecutionRequest,
    AutonomousExecutionResponse,
    OrchestrationCreate,
    OrchestrationRunPublic,
)
from backend.app.services.adaptive_planning import build_adaptive_planning_guidance
from backend.app.services.audit import record_audit
from backend.app.services.command_recovery import CommandRecoveryError, create_recovery_command
from backend.app.services.command_promotion import (
    CommandPromotionError,
    promote_command_to_project,
)
from backend.app.services.autonomous_execution import execute_orchestration_autonomously
from backend.app.services.evidence_execution import prepare_orchestration_research
from backend.app.services.founding_agents import ensure_founding_agents
from backend.app.services.live_planner import build_live_plan
from backend.app.services.orchestrator import create_orchestration_run, refresh_orchestration_status
from backend.app.services.owner_dashboard import build_decision_brief, build_owner_dashboard
from backend.app.services.playbook_engine import consolidate_playbooks
from backend.app.services.playbook_guidance import build_playbook_guidance
from backend.app.services.playbook_overlay import merge_playbook
from backend.app.services.portfolio_governor import (
    PortfolioGovernorError,
    evaluate_project_execution,
)
from backend.app.services.project_delivery import sync_project_delivery_outcome

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
    ensure_founding_agents(
        session,
        organization_id=organization_id,
        created_by_user_id=current_user.id,
    )
    consolidate_playbooks(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    playbook_guidance = build_playbook_guidance(
        session,
        organization_id=organization_id,
        objective=payload.objective,
    )
    adaptive_guidance = build_adaptive_planning_guidance(
        session,
        organization_id=organization_id,
        objective=payload.objective,
    )
    adaptive_guidance = merge_playbook(adaptive_guidance, playbook_guidance)
    planned = build_live_plan(
        payload.objective,
        adaptive_guidance=adaptive_guidance,
    )
    context = {
        **payload.context,
        "owner_command": {"approval_status": "awaiting_approval", "approved_by": None},
        "planner": planned.metadata,
        "operational_playbook": playbook_guidance,
    }
    run = create_orchestration_run(
        session,
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        objective=payload.objective,
        context=context,
        plan=planned.steps,
    )
    run.planner_version = planned.planner_version
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="owner_command.created",
        resource_type="orchestration",
        resource_id=str(run.id),
        details={
            "approval_status": "awaiting_approval",
            "planner_version": planned.planner_version,
            "planner": planned.metadata,
            "operational_playbook": playbook_guidance,
            "step_count": len(planned.steps),
        },
    )
    session.commit()
    session.refresh(run)
    return _to_public(session, run)


@router.get("/{organization_id}/owner-commands", response_model=list[OrchestrationRunPublic])
def list_owner_commands(
    organization_id: UUID, membership: OwnerDep, session: SessionDep
) -> list[OrchestrationRunPublic]:
    _require_owner(membership)
    runs = list(
        session.scalars(
            select(OrchestrationRun)
            .where(OrchestrationRun.organization_id == organization_id)
            .order_by(OrchestrationRun.created_at.desc())
        )
    )
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
    organization_id: UUID,
    run_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    if not _is_owner_command(run):
        raise HTTPException(status_code=404, detail="Owner command not found")
    refresh_orchestration_status(session, run)
    session.commit()
    return build_decision_brief(session, run)


@router.post(
    "/{organization_id}/owner-commands/{run_id}/promote",
    response_model=dict[str, Any],
)
def promote_owner_command(
    organization_id: UUID,
    run_id: UUID,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    if not _is_owner_command(run):
        raise HTTPException(status_code=404, detail="Owner command not found")
    refresh_orchestration_status(session, run)
    try:
        result = promote_command_to_project(
            session,
            run=run,
            actor_user_id=current_user.id,
        )
    except CommandPromotionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return result


@router.post(
    "/{organization_id}/owner-commands/{run_id}/recover",
    response_model=OrchestrationRunPublic,
    status_code=201,
)
def recover_owner_command(
    organization_id: UUID,
    run_id: UUID,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrchestrationRunPublic:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    if not _is_owner_command(run):
        raise HTTPException(status_code=404, detail="Owner command not found")
    refresh_orchestration_status(session, run)
    try:
        recovery = create_recovery_command(
            session,
            source_run=run,
            actor_user_id=current_user.id,
        )
    except CommandRecoveryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    session.refresh(recovery)
    return _to_public(session, recovery)


@router.post(
    "/{organization_id}/owner-commands/{run_id}/approve",
    response_model=OrchestrationRunPublic,
)
def approve_owner_command(
    organization_id: UUID,
    run_id: UUID,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrchestrationRunPublic:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    if not _is_owner_command(run):
        raise HTTPException(status_code=404, detail="Owner command not found")
    run.context = {
        **run.context,
        "owner_command": {
            **run.context["owner_command"],
            "approval_status": "approved",
            "approved_by": str(current_user.id),
        },
    }
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="owner_command.approved",
        resource_type="orchestration",
        resource_id=str(run.id),
        details={},
    )
    session.commit()
    session.refresh(run)
    return _to_public(session, run)


@router.post(
    "/{organization_id}/owner-commands/{run_id}/execute",
    response_model=AutonomousExecutionResponse,
)
def execute_owner_command(
    organization_id: UUID,
    run_id: UUID,
    payload: AutonomousExecutionRequest,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> AutonomousExecutionResponse:
    _require_owner(membership)
    run = _get_run(session, organization_id, run_id)
    command = (run.context or {}).get("owner_command")
    if not command:
        raise HTTPException(status_code=404, detail="Owner command not found")
    if command.get("approval_status") != "approved":
        raise HTTPException(status_code=409, detail="Owner command requires approval")
    delivery_project_id = ((run.context or {}).get("project_delivery") or {}).get(
        "project_id"
    )
    delivery_project = (
        session.get(OrganizationProject, UUID(delivery_project_id))
        if delivery_project_id
        else None
    )
    if delivery_project is None and delivery_project_id:
        candidates = list(
            session.scalars(
                select(OrganizationProject).where(
                    OrganizationProject.organization_id == organization_id
                )
            )
        )
        delivery_project = next(
            (
                item
                for item in candidates
                if str(item.id) == delivery_project_id
                or (item.metadata_json or {}).get("delivery_command_id") == str(run.id)
                or (item.metadata_json or {}).get("recovery_command_id") == str(run.id)
            ),
            None,
        )
    if delivery_project_id and delivery_project is None:
        raise HTTPException(status_code=409, detail="Delivery project could not be resolved")
    if delivery_project is not None:
        try:
            governor = evaluate_project_execution(
                session,
                project=delivery_project,
                run=run,
            )
        except PortfolioGovernorError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        run.context = {
            **(run.context or {}),
            "portfolio_governor": governor,
        }
    prepare_orchestration_research(
        session,
        run=run,
        actor_user_id=current_user.id,
    )
    report = execute_orchestration_autonomously(
        session,
        run=run,
        actor_user_id=current_user.id,
        stop_on_failure=payload.stop_on_failure,
        max_steps=payload.max_steps,
        max_retries_per_step=payload.max_retries_per_step,
        max_upstream_text_chars=payload.max_upstream_text_chars,
    )
    refresh_orchestration_status(session, run)
    delivery_outcome = sync_project_delivery_outcome(
        session,
        run=run,
        actor_user_id=current_user.id,
        project_id=delivery_project_id,
        project=delivery_project,
    )
    if delivery_outcome is not None:
        run.summary = {
            **(run.summary or {}),
            "project_delivery_sync": delivery_outcome,
        }
    session.flush()
    session.commit()
    session.refresh(run)
    return AutonomousExecutionResponse(run=_to_public(session, run), execution=report)
