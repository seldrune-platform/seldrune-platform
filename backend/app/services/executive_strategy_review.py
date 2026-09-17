from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog
from backend.app.services.audit import record_audit

_REVIEW_ACTION = "executive.strategy_reviewed"
_REVIEW_RESOURCE = "executive_strategy_review"


def strategy_review_fingerprint(priority: dict[str, Any]) -> str:
    strategy = priority.get("strategy") or {}
    recommendation = strategy.get("recommendation") or {}
    outcome_score = strategy.get("outcome_score") or {}
    escalation = priority.get("escalation") or {}
    payload = {
        "priority_key": priority.get("key"),
        "selected_mode": strategy.get("mode"),
        "recommended_mode": recommendation.get("recommended_mode"),
        "recommendation_basis": recommendation.get("basis"),
        "recommendation_evidence_strength": recommendation.get("evidence_strength"),
        "recommendation_attempts": recommendation.get("attempts", 0),
        "recommendation_resolution_associations": recommendation.get(
            "resolution_associations", 0
        ),
        "recommendation_resolution_rate": recommendation.get("resolution_rate", 0.0),
        "selected_outcome_score": {
            "family": outcome_score.get("family"),
            "family_attempts": outcome_score.get("family_attempts", 0),
            "attempts": outcome_score.get("attempts", 0),
            "resolution_associations": outcome_score.get("resolution_associations", 0),
            "persisted_after_success": outcome_score.get("persisted_after_success", 0),
            "unsuccessful_attempts": outcome_score.get("unsuccessful_attempts", 0),
            "resolution_rate": outcome_score.get("resolution_rate", 0.0),
            "evidence_strength": outcome_score.get("evidence_strength", "none"),
        },
        "preferred_reference_command_id": strategy.get("preferred_reference_command_id"),
        "avoid_reference_command_ids": sorted(
            str(item) for item in strategy.get("avoid_reference_command_ids") or []
        ),
        "escalation_level": int(escalation.get("level") or 0),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _latest_review_events(
    session: Session,
    organization_id: UUID,
) -> dict[str, AuditLog]:
    events = session.scalars(
        select(AuditLog)
        .where(
            AuditLog.organization_id == organization_id,
            AuditLog.action == _REVIEW_ACTION,
            AuditLog.resource_type == _REVIEW_RESOURCE,
        )
        .order_by(AuditLog.occurred_at.desc())
    )
    latest: dict[str, AuditLog] = {}
    for event in events:
        if event.resource_id and event.resource_id not in latest:
            latest[event.resource_id] = event
    return latest


def _review_state(
    priority: dict[str, Any],
    event: AuditLog | None,
) -> dict[str, Any]:
    strategy = priority.get("strategy") or {}
    selected_mode = str(strategy.get("mode") or "baseline")
    recommendation = strategy.get("recommendation") or {}
    recommended_mode = recommendation.get("recommended_mode")
    required = bool(recommended_mode)
    fingerprint = strategy_review_fingerprint(priority)

    base = {
        "required": required,
        "current": False,
        "status": "not_required" if not required else "pending",
        "selected_mode": selected_mode,
        "recommended_mode": recommended_mode,
        "effective_mode": selected_mode,
        "decision": None,
        "reason": None,
        "event_id": None,
        "reviewed_at": None,
        "actor_user_id": None,
        "evidence_fingerprint": fingerprint,
        "causal_claim": False,
    }
    if not required or event is None:
        return base

    details = event.details or {}
    decision = details.get("decision")
    chosen_mode = details.get("chosen_mode")
    current = (
        details.get("evidence_fingerprint") == fingerprint
        and details.get("selected_mode") == selected_mode
        and details.get("recommended_mode") == recommended_mode
        and (
            (decision == "keep_selected" and chosen_mode == selected_mode)
            or (decision == "use_recommended" and chosen_mode == recommended_mode)
        )
    )
    if not current:
        return {
            **base,
            "status": "stale",
            "decision": decision,
            "reason": details.get("reason"),
            "event_id": str(event.id),
            "reviewed_at": event.occurred_at,
            "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        }

    return {
        **base,
        "current": True,
        "status": (
            "accepted_recommended" if decision == "use_recommended" else "accepted_selected"
        ),
        "effective_mode": str(chosen_mode),
        "decision": decision,
        "reason": details.get("reason"),
        "event_id": str(event.id),
        "reviewed_at": event.occurred_at,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
    }


def build_executive_strategy_reviews(
    session: Session,
    organization_id: UUID,
    priorities: list[dict[str, Any]],
) -> dict[str, Any]:
    events = _latest_review_events(session, organization_id)
    enriched: list[dict[str, Any]] = []
    required = 0
    reviewed = 0
    pending = 0
    stale = 0
    accepted_selected = 0
    accepted_recommended = 0

    for priority in priorities:
        key = str(priority.get("key") or "")
        review = _review_state(priority, events.get(key))
        enriched.append({**priority, "strategy_review": review})
        if review["required"]:
            required += 1
        if review["current"]:
            reviewed += 1
        if review["status"] == "pending":
            pending += 1
        elif review["status"] == "stale":
            stale += 1
        elif review["status"] == "accepted_selected":
            accepted_selected += 1
        elif review["status"] == "accepted_recommended":
            accepted_recommended += 1

    return {
        "priorities": enriched,
        "summary": {
            "review_required": required,
            "reviewed": reviewed,
            "pending": pending,
            "stale": stale,
            "accepted_selected": accepted_selected,
            "accepted_recommended": accepted_recommended,
        },
    }


def record_executive_strategy_review(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    priority: dict[str, Any],
    decision: str,
    reason: str,
) -> AuditLog:
    strategy = priority.get("strategy") or {}
    selected_mode = str(strategy.get("mode") or "baseline")
    recommendation = strategy.get("recommendation") or {}
    recommended_mode = recommendation.get("recommended_mode")
    if not recommended_mode:
        raise ValueError("No comparative strategy recommendation requires review")
    if decision == "keep_selected":
        chosen_mode = selected_mode
    elif decision == "use_recommended":
        chosen_mode = str(recommended_mode)
    else:
        raise ValueError("Unsupported strategy review decision")

    return record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=_REVIEW_ACTION,
        resource_type=_REVIEW_RESOURCE,
        resource_id=str(priority.get("key") or ""),
        details={
            "priority_key": priority.get("key"),
            "selected_mode": selected_mode,
            "recommended_mode": recommended_mode,
            "decision": decision,
            "chosen_mode": chosen_mode,
            "reason": reason,
            "evidence_fingerprint": strategy_review_fingerprint(priority),
            "recommendation_basis": recommendation.get("basis"),
            "recommendation_evidence_strength": recommendation.get(
                "evidence_strength", "none"
            ),
            "recommendation_attempts": recommendation.get("attempts", 0),
            "recommendation_resolution_associations": recommendation.get(
                "resolution_associations", 0
            ),
            "recommendation_resolution_rate": recommendation.get(
                "resolution_rate", 0.0
            ),
            "causal_claim": False,
        },
    )
