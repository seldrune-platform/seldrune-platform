from datetime import UTC, datetime
import hashlib
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _get_run, _to_public
from backend.app.core.rbac import Permission, Role
from backend.app.core.tools import ToolStatus
from backend.app.models.audit import AuditLog
from backend.app.models.governance_policy import GovernancePolicy
from backend.app.models.membership import Membership
from backend.app.models.organization_kernel import OrganizationProject
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.tool_definition import ToolDefinition
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
from backend.app.services.tool_bootstrap import ensure_configured_external_tools
from backend.app.services.tool_input_defaults import external_action_default_fields
from backend.app.services.portfolio_governor import (
    evaluate_project_execution,
    reserve_project_budget,
    revoke_project_budget_reservation,
)
from backend.app.services.project_delivery import sync_project_delivery_outcome

router = APIRouter(prefix="/organizations", tags=["owner-command-center"])
OwnerDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_MANAGE))]


class GovernancePolicyRollback(BaseModel):
    source_event_id: UUID


class GovernancePolicyUpdate(BaseModel):
    max_steps_per_command: int = Field(ge=1, le=100)
    max_project_budget_usd: float = Field(ge=0, le=1_000_000)
    allow_autonomous_execution: bool


def _get_governance_policy(
    session: SessionDep,
    organization_id: UUID,
) -> GovernancePolicy:
    policy = session.get(GovernancePolicy, organization_id)
    if policy is None:
        policy = GovernancePolicy(organization_id=organization_id)
        session.add(policy)
        session.flush()
    return policy


def _governance_policy_public(policy: GovernancePolicy) -> dict[str, Any]:
    return {
        "organization_id": str(policy.organization_id),
        "max_steps_per_command": policy.max_steps_per_command,
        "max_project_budget_usd": policy.max_project_budget_usd,
        "allow_autonomous_execution": policy.allow_autonomous_execution,
        "updated_at": policy.updated_at,
    }


def _require_owner(membership: Membership) -> None:
    if membership.role != Role.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")


def _is_owner_command(run: OrchestrationRun) -> bool:
    return bool((run.context or {}).get("owner_command"))


@router.get("/{organization_id}/governance-policy", response_model=dict[str, Any])
def get_governance_policy(
    organization_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    policy = _get_governance_policy(session, organization_id)
    session.commit()
    return _governance_policy_public(policy)


@router.get(
    "/{organization_id}/governance-policy/history",
    response_model=dict[str, Any],
)
def get_governance_policy_history(
    organization_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    _require_owner(membership)
    events = list(
        session.scalars(
            select(AuditLog)
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.action.in_(
                    ("governance.policy_updated", "governance.policy_rolled_back")
                ),
            )
            .order_by(AuditLog.occurred_at.desc())
            .limit(limit)
        )
    )
    return {
        "total_returned": len(events),
        "revisions": [
            {
                "event_id": str(event.id),
                "action": event.action,
                "policy": (event.details or {}).get("current", {}),
                "actor_user_id": (
                    str(event.actor_user_id) if event.actor_user_id else None
                ),
                "occurred_at": event.occurred_at,
                "source_event_id": (event.details or {}).get("source_event_id"),
            }
            for event in events
        ],
    }


@router.post(
    "/{organization_id}/governance-policy/rollback",
    response_model=dict[str, Any],
)
def rollback_governance_policy(
    organization_id: UUID,
    payload: GovernancePolicyRollback,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    source = session.get(AuditLog, payload.source_event_id)
    if (
        source is None
        or source.organization_id != organization_id
        or source.action
        not in ("governance.policy_updated", "governance.policy_rolled_back")
    ):
        raise HTTPException(status_code=404, detail="Governance policy revision not found")
    snapshot = (source.details or {}).get("current")
    try:
        target = GovernancePolicyUpdate.model_validate(snapshot)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail="Governance policy revision is invalid or incomplete",
        ) from exc
    policy = _get_governance_policy(session, organization_id)
    previous = jsonable_encoder(_governance_policy_public(policy))
    policy.max_steps_per_command = target.max_steps_per_command
    policy.max_project_budget_usd = target.max_project_budget_usd
    policy.allow_autonomous_execution = target.allow_autonomous_execution
    session.flush()
    current = jsonable_encoder(_governance_policy_public(policy))
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="governance.policy_rolled_back",
        resource_type="governance_policy",
        resource_id=str(organization_id),
        details={
            "source_event_id": str(source.id),
            "previous": previous,
            "current": current,
        },
    )
    session.commit()
    session.refresh(policy)
    return _governance_policy_public(policy)


@router.post(
    "/{organization_id}/governance-policy/preview",
    response_model=dict[str, Any],
)
def preview_governance_policy(
    organization_id: UUID,
    payload: GovernancePolicyUpdate,
    membership: OwnerDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    current = _get_governance_policy(session, organization_id)
    runs = [
        run
        for run in session.scalars(
            select(OrchestrationRun).where(
                OrchestrationRun.organization_id == organization_id
            )
        )
        if _is_owner_command(run)
    ]
    run_ids = {run.id for run in runs}
    step_counts = {run_id: 0 for run_id in run_ids}
    if run_ids:
        for step in session.scalars(
            select(OrchestrationStep).where(
                OrchestrationStep.orchestration_run_id.in_(run_ids)
            )
        ):
            step_counts[step.orchestration_run_id] += 1
    blocked_commands = [
        {
            "id": str(run.id),
            "objective": run.objective,
            "step_count": step_counts[run.id],
            "limit": payload.max_steps_per_command,
            "reason": "command_step_limit",
        }
        for run in runs
        if step_counts[run.id] > payload.max_steps_per_command
    ]
    projects = list(
        session.scalars(
            select(OrganizationProject).where(
                OrganizationProject.organization_id == organization_id
            )
        )
    )
    blocked_projects = [
        {
            "id": str(project.id),
            "name": project.name,
            "budget_limit_usd": project.budget_limit_usd,
            "limit_usd": payload.max_project_budget_usd,
            "reason": "project_budget_limit",
        }
        for project in projects
        if project.budget_limit_usd > payload.max_project_budget_usd
    ]
    autonomous_change = (
        current.allow_autonomous_execution != payload.allow_autonomous_execution
    )
    return {
        "safe_to_apply": not blocked_commands and not blocked_projects,
        "commands_evaluated": len(runs),
        "commands_blocked": len(blocked_commands),
        "projects_evaluated": len(projects),
        "projects_blocked": len(blocked_projects),
        "autonomous_execution": {
            "current": current.allow_autonomous_execution,
            "proposed": payload.allow_autonomous_execution,
            "changes": autonomous_change,
        },
        "blocked_commands": blocked_commands,
        "blocked_projects": blocked_projects,
    }


@router.put("/{organization_id}/governance-policy", response_model=dict[str, Any])
def update_governance_policy(
    organization_id: UUID,
    payload: GovernancePolicyUpdate,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    policy = _get_governance_policy(session, organization_id)
    previous = _governance_policy_public(policy)
    policy.max_steps_per_command = payload.max_steps_per_command
    policy.max_project_budget_usd = payload.max_project_budget_usd
    policy.allow_autonomous_execution = payload.allow_autonomous_execution
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="governance.policy_updated",
        resource_type="governance_policy",
        resource_id=str(organization_id),
        details={
            "previous": jsonable_encoder(previous),
            "current": jsonable_encoder(_governance_policy_public(policy)),
        },
    )
    session.commit()
    session.refresh(policy)
    return _governance_policy_public(policy)


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
    ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    active_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == ToolStatus.ACTIVE.value,
            )
        )
    )
    tool_catalog: list[dict[str, Any]] = []
    for tool in active_tools:
        input_defaults = external_action_default_fields(
            session,
            tool=tool,
            requested_by_user_id=current_user.id,
        )
        planner_schema = dict(tool.input_schema or {})
        required_fields = planner_schema.get("required")
        if isinstance(required_fields, list) and input_defaults:
            planner_schema["required"] = [
                field
                for field in required_fields
                if field not in input_defaults
            ]
        tool_catalog.append(
            {
                "slug": tool.slug,
                "description": tool.description,
                "provider": tool.provider,
                "action_name": tool.action_name,
                "risk_level": tool.risk_level,
                "input_schema": planner_schema,
                "input_defaults": input_defaults,
            }
        )
    planned = build_live_plan(
        payload.objective,
        adaptive_guidance=adaptive_guidance,
        available_tools=tool_catalog,
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


def _canonical_evidence_bytes(evidence: dict[str, Any]) -> bytes:
    encoded = jsonable_encoder(evidence)
    return json.dumps(
        encoded,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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
    evidence = jsonable_encoder(
        {
            "schema_version": "1.0",
            "organization_id": str(organization_id),
            "generated_at": datetime.now(UTC),
            "event_count": len(events),
            "events": events,
        }
    )
    digest = hashlib.sha256(_canonical_evidence_bytes(evidence)).hexdigest()
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


@router.post("/{organization_id}/audit-export/verify", response_model=dict[str, Any])
def verify_governance_evidence(
    organization_id: UUID,
    package: dict[str, Any],
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    integrity = package.get("integrity")
    evidence = {key: value for key, value in package.items() if key != "integrity"}
    provided_digest = integrity.get("digest") if isinstance(integrity, dict) else None
    algorithm = integrity.get("algorithm") if isinstance(integrity, dict) else None
    event_count = len(evidence.get("events", [])) if isinstance(evidence.get("events"), list) else 0
    expected_digest = hashlib.sha256(_canonical_evidence_bytes(evidence)).hexdigest()
    reason = "Evidence package is authentic and unchanged."
    valid = True
    if evidence.get("organization_id") != str(organization_id):
        valid = False
        reason = "Evidence belongs to a different organization."
    elif evidence.get("schema_version") != "1.0":
        valid = False
        reason = "Evidence schema is unsupported."
    elif algorithm != "SHA-256" or not provided_digest:
        valid = False
        reason = "Integrity metadata is missing or unsupported."
    elif provided_digest != expected_digest:
        valid = False
        reason = "Integrity digest does not match; evidence may have been altered."
    elif evidence.get("event_count") != event_count:
        valid = False
        reason = "Event count does not match the evidence contents."

    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="audit.evidence_verified" if valid else "audit.evidence_rejected",
        resource_type="audit_log",
        resource_id=provided_digest,
        details={
            "valid": valid,
            "reason": reason,
            "event_count": event_count,
            "provided_digest": provided_digest,
            "expected_digest": expected_digest,
        },
    )
    session.commit()
    return {
        "valid": valid,
        "reason": reason,
        "event_count": event_count,
        "provided_digest": provided_digest,
        "expected_digest": expected_digest,
        "algorithm": "SHA-256",
    }


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
    policy = _get_governance_policy(session, organization_id)
    step_count = len(
        list(
            session.scalars(
                select(OrchestrationStep).where(OrchestrationStep.orchestration_run_id == run.id)
            )
        )
    )
    if step_count > policy.max_steps_per_command:
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="governance.approval_blocked",
            resource_type="orchestration",
            resource_id=str(run.id),
            details={
                "reason": "command_step_limit",
                "step_count": step_count,
                "max_steps_per_command": policy.max_steps_per_command,
            },
        )
        session.commit()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Governance policy allows at most "
                f"{policy.max_steps_per_command} command steps"
            ),
        )
    delivery_context = (run.context or {}).get("project_delivery") or {}
    delivery_project_id = delivery_context.get("project_id")
    delivery_project = (
        session.get(OrganizationProject, UUID(delivery_project_id))
        if delivery_project_id
        else None
    )
    if (
        delivery_project is not None
        and delivery_project.budget_limit_usd > policy.max_project_budget_usd
    ):
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="governance.approval_blocked",
            resource_type="organization_project",
            resource_id=str(delivery_project.id),
            details={
                "reason": "project_budget_limit",
                "project_budget_usd": delivery_project.budget_limit_usd,
                "max_project_budget_usd": policy.max_project_budget_usd,
            },
        )
        session.commit()
        raise HTTPException(
            status_code=409,
            detail="Project budget exceeds the organization governance policy",
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
    policy = _get_governance_policy(session, organization_id)
    if not policy.allow_autonomous_execution:
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="governance.execution_blocked",
            resource_type="orchestration",
            resource_id=str(run.id),
            details={"reason": "autonomous_execution_disabled"},
        )
        session.commit()
        raise HTTPException(
            status_code=409,
            detail="Autonomous execution is disabled by governance policy",
        )
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
