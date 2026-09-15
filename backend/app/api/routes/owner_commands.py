from datetime import UTC, datetime
import hashlib
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _get_run, _to_public
from backend.app.core.rbac import Permission, Role
from backend.app.models.audit import AuditLog
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
    evaluate_project_execution,
    reserve_project_budget,
    revoke_project_budget_reservation,
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


_SENSITIVE_AUDIT_KEYS = ("secret", "token", "password", "api_key", "authorization")


def _sanitize_audit_details(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[redacted]"
                if any(marker in key.lower() for marker in _SENSITIVE_AUDIT_KEYS)
                else _sanitize_audit_details(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_audit_details(item) for item in value]
    return value


def _audit_severity(action: str) -> str:
    if any(marker in action for marker in ("failed", "blocked", "triggered")):
        return "warning"
    if any(marker in action for marker in ("approved", "revoked", "budget", "resource")):
        return "governance"
    return "info"


def _audit_event_payload(event: AuditLog) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "action": event.action,
        "severity": _audit_severity(event.action),
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "details": _sanitize_audit_details(event.details or {}),
        "occurred_at": event.occurred_at,
    }


@router.get("/{organization_id}/audit-log", response_model=dict[str, Any])
def get_governance_audit_log(
    organization_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, max_length=120),
) -> dict[str, Any]:
    _require_owner(membership)
    statement = select(AuditLog).where(AuditLog.organization_id == organization_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    events = list(
        session.scalars(statement.order_by(AuditLog.occurred_at.desc()).limit(limit))
    )
    return {
        "total_returned": len(events),
        "filters": {"action": action, "limit": limit},
        "events": [_audit_event_payload(event) for event in events],
    }


@router.post("/{organization_id}/audit-export", response_model=dict[str, Any])
def export_governance_evidence(
    organization_id: UUID,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    _require_owner(membership)
    records = list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.occurred_at.asc())
            .limit(limit)
        )
    )
    events = [_audit_event_payload(event) for event in records]
    evidence = {
        "schema_version": "1.0",
        "organization_id": str(organization_id),
        "generated_at": datetime.now(UTC),
        "event_count": len(events),
        "events": events,
    }
    canonical = json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    package = {
        **evidence,
        "integrity": {
            "algorithm": "SHA-256",
            "digest": digest,
            "scope": "canonical JSON of all top-level fields except integrity",
        },
    }
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="audit.evidence_exported",
        resource_type="audit_log",
        resource_id=digest,
        details={"event_count": len(events), "limit": limit, "digest": digest},
    )
    session.commit()
    return package


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
    delivery_context = (run.context or {}).get("project_delivery") or {}
    delivery_project_id = delivery_context.get("project_id")
    delivery_project = (
        session.get(OrganizationProject, UUID(delivery_project_id))
        if delivery_project_id
        else None
    )
    governor = (
        evaluate_project_execution(
            project=delivery_project,
            run=run,
            delivery_context=delivery_context,
        )
        if delivery_project_id
        else None
    )
    if governor is not None and not governor["allowed"]:
        raise HTTPException(status_code=409, detail="; ".join(governor["reasons"]))
    reservation = (
        reserve_project_budget(
            project=delivery_project,
            run=run,
            amount_usd=float(governor["estimated_execution_cost_usd"]),
            actor_user_id=str(current_user.id),
        )
        if delivery_project is not None and governor is not None
        else None
    )
    if governor is not None and reservation is not None:
        governor = {**governor, "budget_reservation": reservation}
    run.context = {
        **run.context,
        **({"portfolio_governor": governor} if governor is not None else {}),
        "owner_command": {
            **run.context["owner_command"],
            "approval_status": "approved",
            "approved_by": str(current_user.id),
            **({"portfolio_governor": governor} if governor is not None else {}),
        },
    }
    flag_modified(run, "context")
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="owner_command.approved",
        resource_type="orchestration",
        resource_id=str(run.id),
        details={
            **({"budget_reservation": reservation} if reservation is not None else {}),
        },
    )
    session.commit()
    session.refresh(run)
    return _to_public(session, run)


@router.post(
    "/{organization_id}/owner-commands/{run_id}/revoke",
    response_model=OrchestrationRunPublic,
)
def revoke_owner_command_approval(
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
    command = (run.context or {}).get("owner_command") or {}
    if command.get("approval_status") == "revoked":
        return _to_public(session, run)
    if command.get("approval_status") != "approved":
        raise HTTPException(status_code=409, detail="Only an approved command can be revoked")
    if int((run.summary or {}).get("succeeded_steps", 0)) > 0:
        raise HTTPException(
            status_code=409,
            detail="Approval cannot be revoked after execution has started",
        )

    delivery_context = (run.context or {}).get("project_delivery") or {}
    project_id = delivery_context.get("project_id")
    project = (
        session.get(OrganizationProject, UUID(project_id))
        if project_id
        else None
    )
    released = (
        revoke_project_budget_reservation(
            project=project,
            command_id=str(run.id),
            actor_user_id=str(current_user.id),
        )
        if project is not None
        else None
    )
    governor = (run.context or {}).get("portfolio_governor") or {}
    if released is not None:
        governor = {**governor, "budget_reservation": released}
    run.context = {
        **(run.context or {}),
        **({"portfolio_governor": governor} if governor else {}),
        "owner_command": {
            **command,
            "approval_status": "revoked",
            "approved_by": None,
            "revoked_by": str(current_user.id),
            **({"budget_reservation": released} if released is not None else {}),
        },
    }
    flag_modified(run, "context")
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="owner_command.approval_revoked",
        resource_type="orchestration",
        resource_id=str(run.id),
        details={
            **({"budget_reservation": released} if released is not None else {}),
        },
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
    approved_governor = (run.context or {}).get("portfolio_governor") or command.get(
        "portfolio_governor"
    )
    if isinstance(approved_governor, dict) and not approved_governor.get("allowed", False):
        raise HTTPException(
            status_code=409,
            detail="; ".join(approved_governor.get("reasons") or ["Execution denied"]),
        )
    if isinstance(approved_governor, dict):
        run.summary = {
            **(run.summary or {}),
            "portfolio_governor": approved_governor,
        }
        flag_modified(run, "summary")
        session.flush()
    delivery_context = (run.context or {}).get("project_delivery") or {}
    delivery_project_id = delivery_context.get("project_id")
    delivery_project = (
        session.get(OrganizationProject, UUID(delivery_project_id))
        if delivery_project_id
        else None
    )
    if delivery_project is None:
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
                or f'Deliver the organization project "{item.name}"' in run.objective
            ),
            None,
        )
    if delivery_project is not None:
        delivery_project_id = str(delivery_project.id)
        delivery_context = {
            **delivery_context,
            "project_id": delivery_project_id,
            "budget_limit_usd": delivery_project.budget_limit_usd,
            "budget_spent_usd": delivery_project.budget_spent_usd,
            "resource_limit_units": delivery_project.resource_limit_units,
            "resource_used_units": delivery_project.resource_used_units,
        }
    if delivery_project_id:
        governor = evaluate_project_execution(
            project=delivery_project,
            run=run,
            delivery_context=delivery_context,
        )
        if not governor["allowed"]:
            raise HTTPException(status_code=409, detail="; ".join(governor["reasons"]))
        approved_reservation = (
            approved_governor.get("budget_reservation")
            if isinstance(approved_governor, dict)
            else None
        )
        if approved_reservation is not None:
            governor = {**governor, "budget_reservation": approved_reservation}
        run.context = {
            **(run.context or {}),
            "portfolio_governor": governor,
        }
        flag_modified(run, "context")
        run.summary = {
            **(run.summary or {}),
            "portfolio_governor": governor,
        }
        flag_modified(run, "summary")
        session.flush()
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
