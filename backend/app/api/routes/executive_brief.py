from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import (
    CurrentUserDep,
    SessionDep,
    require_org_permission,
)
from backend.app.api.routes.orchestrations import _to_public
from backend.app.api.routes.owner_commands import create_owner_command
from backend.app.core.rbac import Permission, Role
from backend.app.models.membership import Membership
from backend.app.models.orchestration import OrchestrationRun
from backend.app.schemas.orchestration import OrchestrationCreate, OrchestrationRunPublic
from backend.app.services.executive_action_lifecycle import reconcile_executive_actions
from backend.app.services.executive_briefing import build_executive_brief
from backend.app.services.executive_outcome_memory import build_executive_outcome_memory
from backend.app.services.executive_strategy import evaluate_executive_strategies
from backend.app.services.executive_strategy_outcomes import (
    build_executive_strategy_outcomes,
)

router = APIRouter(prefix="/organizations", tags=["executive-brief"])
OwnerDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_MANAGE))]


def _require_owner(membership: Membership) -> None:
    if membership.role != Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role required",
        )


def _existing_priority_command(
    session: SessionDep,
    organization_id: UUID,
    priority_key: str,
) -> OrchestrationRun | None:
    runs = session.scalars(
        select(OrchestrationRun)
        .where(OrchestrationRun.organization_id == organization_id)
        .order_by(OrchestrationRun.created_at.desc())
    )
    for run in runs:
        priority = ((run.context or {}).get("executive_priority") or {})
        if priority.get("key") == priority_key and run.status in {"planned", "active"}:
            return run
    return None


def _brief_with_lifecycle(
    session: SessionDep,
    organization_id: UUID,
) -> dict[str, Any]:
    brief = build_executive_brief(session, organization_id)
    lifecycle = reconcile_executive_actions(
        session,
        organization_id,
        brief["priorities"],
    )
    memory = build_executive_outcome_memory(
        session,
        organization_id,
        lifecycle["priorities"],
    )
    outcomes = build_executive_strategy_outcomes(
        session,
        organization_id,
        memory["priorities"],
    )
    strategy = evaluate_executive_strategies(outcomes["priorities"])
    brief["priorities"] = strategy["priorities"]
    brief["executive_actions"] = lifecycle["summary"]
    brief["resolved_actions"] = lifecycle["resolved_recent"]
    brief["outcome_memory"] = memory["summary"]
    brief["outcome_playbooks"] = memory["playbooks"]
    brief["executive_strategy"] = strategy["summary"]
    brief["strategy_outcomes"] = outcomes["summary"]
    brief["strategy_scorecards"] = outcomes["scorecards"]
    brief["strategy_outcome_history"] = outcomes["recent"]
    return brief


def _action_objective(priority: dict[str, Any]) -> str:
    action = priority.get("action") or {}
    objective = action["objective"]
    escalation = priority.get("escalation") or {}
    level = int(escalation.get("level") or 0)
    if level:
        completed = int(escalation.get("completed_attempts") or 0)
        objective = (
            f"Executive escalation level {level}: this priority remains after "
            f"{completed} completed governed action attempt(s). Do not simply repeat the "
            "previous plan. Review the prior command evidence and outcomes, identify why the "
            "condition persists, and use a materially different recovery strategy with explicit "
            f"verification criteria. {objective}"
        )

    strategy = priority.get("strategy") or {}
    mode = strategy.get("mode")
    if mode and mode != "observe":
        evidence = " ".join(str(item) for item in strategy.get("required_evidence") or [])
        objective += (
            f" Executive strategy mode {mode}: {strategy.get('rationale', '')} "
            f"Required evidence: {evidence}"
        )

    recommendation = strategy.get("recommendation") or {}
    recommended_mode = recommendation.get("recommended_mode")
    if recommended_mode:
        rate = round(float(recommendation.get("resolution_rate") or 0.0) * 100)
        objective += (
            " Comparative historical scorecards suggest considering strategy mode "
            f"{recommended_mode} ({recommendation.get('evidence_strength', 'none')} evidence; "
            f"{recommendation.get('attempts', 0)} attempts; {rate}% resolution association). "
            "This recommendation is advisory, is not automatically applied, and does not prove "
            "causation. The owner must review current evidence before changing strategy."
        )

    memory = priority.get("outcome_memory") or {}
    preferred = memory.get("preferred_pattern") or {}
    avoid = memory.get("avoid_patterns") or []
    if preferred:
        reference = str(preferred.get("objective") or "")[:900]
        objective += (
            " Organization outcome memory contains a resolution-associated pattern for this "
            f"priority family from command {preferred.get('command_id')}: {reference} "
            "Treat this as supporting evidence rather than proof of causation; adapt it to current "
            "conditions instead of copying it blindly."
        )
    if avoid:
        failed = "; ".join(
            f"{item.get('command_status')} command {item.get('command_id')}: "
            f"{str(item.get('objective') or '')[:350]}"
            for item in avoid[:3]
        )
        objective += (
            " Outcome memory also contains unsuccessful patterns. Do not repeat them without "
            f"explicit evidence-based justification: {failed}."
        )
    return objective[:8000]


def _memory_context(priority: dict[str, Any]) -> dict[str, Any]:
    memory = priority.get("outcome_memory") or {}
    preferred = memory.get("preferred_pattern") or {}
    avoid = memory.get("avoid_patterns") or []
    return {
        "family": memory.get("family"),
        "confidence": memory.get("confidence", "none"),
        "resolution_patterns": memory.get("resolution_patterns", 0),
        "unsuccessful_patterns": memory.get("unsuccessful_patterns", 0),
        "preferred_reference_command_id": preferred.get("command_id"),
        "avoid_reference_command_ids": [item.get("command_id") for item in avoid[:3]],
        "causal_claim": False,
    }


def _strategy_context(priority: dict[str, Any]) -> dict[str, Any]:
    strategy = priority.get("strategy") or {}
    outcome_score = strategy.get("outcome_score") or {}
    recommendation = strategy.get("recommendation") or {}
    return {
        "mode": strategy.get("mode", "baseline"),
        "rationale": strategy.get("rationale"),
        "confidence": strategy.get("confidence", "none"),
        "history_informed": bool(strategy.get("history_informed")),
        "preferred_reference_command_id": strategy.get("preferred_reference_command_id"),
        "avoid_reference_command_ids": strategy.get("avoid_reference_command_ids") or [],
        "required_evidence": strategy.get("required_evidence") or [],
        "outcome_score": {
            "family": outcome_score.get("family"),
            "family_attempts": outcome_score.get("family_attempts", 0),
            "attempts": outcome_score.get("attempts", 0),
            "resolution_associations": outcome_score.get("resolution_associations", 0),
            "persisted_after_success": outcome_score.get("persisted_after_success", 0),
            "unsuccessful_attempts": outcome_score.get("unsuccessful_attempts", 0),
            "resolution_rate": outcome_score.get("resolution_rate", 0.0),
            "evidence_strength": outcome_score.get("evidence_strength", "none"),
            "causal_claim": False,
        },
        "recommendation": {
            "selected_mode": recommendation.get("selected_mode"),
            "recommended_mode": recommendation.get("recommended_mode"),
            "basis": recommendation.get("basis"),
            "evidence_strength": recommendation.get("evidence_strength", "none"),
            "attempts": recommendation.get("attempts", 0),
            "resolution_associations": recommendation.get("resolution_associations", 0),
            "resolution_rate": recommendation.get("resolution_rate", 0.0),
            "auto_applied": False,
            "owner_review_required": True,
            "causal_claim": False,
        },
        "owner_approval_required": True,
        "causal_claim": False,
    }


@router.get("/{organization_id}/executive-brief", response_model=dict[str, Any])
def get_executive_brief(
    organization_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    return _brief_with_lifecycle(session, organization_id)


@router.post(
    "/{organization_id}/executive-brief/actions/{priority_key}",
    response_model=OrchestrationRunPublic,
    status_code=201,
)
def create_executive_priority_action(
    organization_id: UUID,
    priority_key: str,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrchestrationRunPublic:
    _require_owner(membership)
    brief = _brief_with_lifecycle(session, organization_id)
    priority = next(
        (item for item in brief["priorities"] if item.get("key") == priority_key),
        None,
    )
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Executive priority is no longer active; refresh the brief",
        )
    action = priority.get("action") or {}
    if action.get("kind") != "owner_command" or not action.get("objective"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This priority is informational or navigational and does not "
                "create a command"
            ),
        )

    existing = _existing_priority_command(session, organization_id, priority_key)
    if existing is not None:
        return _to_public(session, existing)

    escalation = priority.get("escalation") or {}
    payload = OrchestrationCreate(
        objective=_action_objective(priority),
        context={
            "executive_priority": {
                "key": priority["key"],
                "severity": priority["severity"],
                "effective_severity": escalation.get("effective_severity"),
                "escalation_level": escalation.get("level", 0),
                "completed_attempts": escalation.get("completed_attempts", 0),
                "source": priority["source"],
                "resource_id": priority.get("resource_id"),
                "title": priority["title"],
            },
            "executive_outcome_memory": _memory_context(priority),
            "executive_strategy": _strategy_context(priority),
        },
    )
    return create_owner_command(
        organization_id,
        payload,
        membership,
        current_user,
        session,
    )
