from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
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
from backend.app.services.executive_strategy import (
    evaluate_executive_strategies,
    strategy_mode_guidance,
)
from backend.app.services.executive_strategy_outcomes import (
    build_executive_strategy_outcomes,
)
from backend.app.services.executive_strategy_review import (
    build_executive_strategy_reviews,
    record_executive_strategy_review,
)
from backend.app.services.executive_strategy_review_outcomes import (
    build_executive_strategy_review_outcomes,
)

router = APIRouter(prefix="/organizations", tags=["executive-brief"])
OwnerDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_MANAGE))]


class ExecutiveStrategyReviewRequest(BaseModel):
    decision: Literal["keep_selected", "use_recommended"]
    reason: str = Field(min_length=3, max_length=1000)


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
    reviews = build_executive_strategy_reviews(
        session,
        organization_id,
        strategy["priorities"],
    )
    review_outcomes = build_executive_strategy_review_outcomes(
        session,
        organization_id,
        reviews["priorities"],
    )
    brief["priorities"] = review_outcomes["priorities"]
    brief["executive_actions"] = lifecycle["summary"]
    brief["resolved_actions"] = lifecycle["resolved_recent"]
    brief["outcome_memory"] = memory["summary"]
    brief["outcome_playbooks"] = memory["playbooks"]
    brief["executive_strategy"] = strategy["summary"]
    brief["executive_strategy_review"] = reviews["summary"]
    brief["strategy_review_outcomes"] = review_outcomes["summary"]
    brief["strategy_review_scorecards"] = review_outcomes["scorecards"]
    brief["strategy_review_outcome_history"] = review_outcomes["recent"]
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
    review = priority.get("strategy_review") or {}
    effective_mode = review.get("effective_mode") or strategy.get("mode")
    if effective_mode and effective_mode != "observe":
        guidance = strategy_mode_guidance(str(effective_mode))
        evidence = " ".join(str(item) for item in guidance["required_evidence"])
        objective += (
            f" Executive strategy mode {effective_mode}: {guidance['rationale']} "
            f"Required evidence: {evidence}"
        )

    if review.get("current"):
        objective += (
            " Owner strategy review is current for this evidence snapshot: "
            f"selected mode {review.get('selected_mode')}, effective mode "
            f"{review.get('effective_mode')}, decision {review.get('decision')}. "
            f"Review rationale: {review.get('reason')}."
        )

    recommendation = strategy.get("recommendation") or {}
    recommended_mode = recommendation.get("recommended_mode")
    if recommended_mode:
        rate = round(float(recommendation.get("resolution_rate") or 0.0) * 100)
        objective += (
            " Comparative historical scorecards suggest considering strategy mode "
            f"{recommended_mode} ({recommendation.get('evidence_strength', 'none')} evidence; "
            f"{recommendation.get('attempts', 0)} attempts; {rate}% resolution association). "
            "This recommendation is not automatically applied and does not prove causation."
        )

    review_outcomes = priority.get("strategy_review_outcomes") or {}
    if review_outcomes.get("total_reviewed_attempts"):
        objective += (
            " Historical owner review outcomes are available for this priority family. "
            "Treat those decision-outcome associations as supporting evidence only; they do not "
            "prove that choosing or rejecting a recommendation caused the later outcome."
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
    review = priority.get("strategy_review") or {}
    review_outcomes = priority.get("strategy_review_outcomes") or {}
    selected_mode = strategy.get("mode", "baseline")
    effective_mode = review.get("effective_mode") or selected_mode
    guidance = strategy_mode_guidance(str(effective_mode))
    reviewed_at = review.get("reviewed_at")
    if reviewed_at is not None and hasattr(reviewed_at, "isoformat"):
        reviewed_at = reviewed_at.isoformat()
    return {
        "mode": effective_mode,
        "selected_mode": selected_mode,
        "rationale": guidance["rationale"],
        "confidence": strategy.get("confidence", "none"),
        "history_informed": bool(strategy.get("history_informed")),
        "preferred_reference_command_id": strategy.get("preferred_reference_command_id"),
        "avoid_reference_command_ids": strategy.get("avoid_reference_command_ids") or [],
        "required_evidence": guidance["required_evidence"],
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
        "review": {
            "required": bool(review.get("required")),
            "current": bool(review.get("current")),
            "status": review.get("status"),
            "decision": review.get("decision"),
            "reason": review.get("reason"),
            "event_id": review.get("event_id"),
            "selected_mode": review.get("selected_mode"),
            "recommended_mode": review.get("recommended_mode"),
            "effective_mode": effective_mode,
            "reviewed_at": reviewed_at,
            "actor_user_id": review.get("actor_user_id"),
            "evidence_fingerprint": review.get("evidence_fingerprint"),
            "causal_claim": False,
        },
        "review_outcomes": {
            "family": review_outcomes.get("family"),
            "total_reviewed_attempts": review_outcomes.get("total_reviewed_attempts", 0),
            "resolution_associations": review_outcomes.get("resolution_associations", 0),
            "decision_evidence": review_outcomes.get("decision_evidence") or {},
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
    "/{organization_id}/executive-brief/strategy-reviews/{priority_key}",
    response_model=dict[str, Any],
)
def review_executive_strategy(
    organization_id: UUID,
    priority_key: str,
    payload: ExecutiveStrategyReviewRequest,
    membership: OwnerDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
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
    review = priority.get("strategy_review") or {}
    if not review.get("required"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No comparative strategy recommendation requires owner review",
        )
    try:
        event = record_executive_strategy_review(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            priority=priority,
            decision=payload.decision,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    session.commit()
    session.refresh(event)

    refreshed = _brief_with_lifecycle(session, organization_id)
    current = next(
        (item for item in refreshed["priorities"] if item.get("key") == priority_key),
        None,
    )
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Executive priority changed during review; refresh the brief",
        )
    return current["strategy_review"]


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

    review = priority.get("strategy_review") or {}
    if review.get("required") and not review.get("current"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Executive strategy recommendation requires a current owner review "
                "before command creation"
            ),
        )

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
