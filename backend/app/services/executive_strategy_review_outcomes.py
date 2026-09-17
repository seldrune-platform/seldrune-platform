from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.orchestration import OrchestrationRun
from backend.app.services.executive_advisory_calibration import (
    build_executive_advisory_calibration,
)
from backend.app.services.executive_advisory_confidence import (
    build_executive_advisory_confidence_guardrails,
)
from backend.app.services.executive_decision_advisory import decision_advisory
from backend.app.services.executive_strategy_review import build_executive_strategy_reviews

_TERMINAL_STATUSES = {"succeeded", "partial", "failed", "cancelled"}
_UNSUCCESSFUL_STATUSES = {"partial", "failed", "cancelled"}
_REVIEW_DECISIONS = {"keep_selected", "use_recommended"}


def _priority(run: OrchestrationRun) -> dict[str, Any]:
    value = (run.context or {}).get("executive_priority") or {}
    return value if isinstance(value, dict) else {}


def _strategy(run: OrchestrationRun) -> dict[str, Any]:
    value = (run.context or {}).get("executive_strategy") or {}
    return value if isinstance(value, dict) else {}


def _review(strategy: dict[str, Any]) -> dict[str, Any]:
    value = strategy.get("review") or {}
    return value if isinstance(value, dict) else {}


def _family_from_key(key: str) -> str:
    return key.split(":", 1)[0]


def _family(priority: dict[str, Any]) -> str:
    key = str(priority.get("key") or "")
    return _family_from_key(key) if key else str(priority.get("source") or "unknown")


def _evidence_strength(attempts: int, resolutions: int) -> str:
    if resolutions >= 2 and attempts >= 3:
        return "high"
    if resolutions >= 1 and attempts >= 2:
        return "medium"
    if attempts >= 1:
        return "low"
    return "none"


def _empty_scorecard(family: str, decision: str, effective_mode: str) -> dict[str, Any]:
    return {
        "family": family,
        "decision": decision,
        "effective_mode": effective_mode,
        "attempts": 0,
        "execution_succeeded": 0,
        "resolution_associations": 0,
        "persisted_after_success": 0,
        "unsuccessful_attempts": 0,
        "resolution_rate": 0.0,
        "evidence_strength": "none",
        "causal_claim": False,
    }


def _choice_score(
    cards: list[dict[str, Any]],
    *,
    family: str,
    decision: str,
    effective_mode: str | None,
) -> dict[str, Any]:
    if not effective_mode:
        return _empty_scorecard(family, decision, "none")
    matches = [
        card
        for card in cards
        if card["family"] == family
        and card["decision"] == decision
        and card["effective_mode"] == effective_mode
    ]
    result = _empty_scorecard(family, decision, effective_mode)
    for card in matches:
        for field in (
            "attempts",
            "execution_succeeded",
            "resolution_associations",
            "persisted_after_success",
            "unsuccessful_attempts",
        ):
            result[field] += int(card[field])
    attempts = int(result["attempts"])
    resolutions = int(result["resolution_associations"])
    result["resolution_rate"] = round(resolutions / attempts, 4) if attempts else 0.0
    result["evidence_strength"] = _evidence_strength(attempts, resolutions)
    return result


def build_executive_strategy_review_outcomes(
    session: Session,
    organization_id: UUID,
    priorities: list[dict[str, Any]],
) -> dict[str, Any]:
    current_keys = {str(item.get("key")) for item in priorities if item.get("key")}
    scorecards: dict[tuple[str, str, str], dict[str, Any]] = {}
    recent: list[dict[str, Any]] = []

    runs = list(
        session.scalars(
            select(OrchestrationRun)
            .where(OrchestrationRun.organization_id == organization_id)
            .order_by(OrchestrationRun.updated_at.desc())
        )
    )
    for run in runs:
        if run.status not in _TERMINAL_STATUSES:
            continue
        priority = _priority(run)
        strategy = _strategy(run)
        review = _review(strategy)
        key = priority.get("key")
        decision = review.get("decision")
        effective_mode = review.get("effective_mode") or strategy.get("mode")
        if (
            not key
            or decision not in _REVIEW_DECISIONS
            or not effective_mode
            or not review.get("current")
        ):
            continue

        family = _family_from_key(str(key))
        card_key = (family, str(decision), str(effective_mode))
        card = scorecards.setdefault(card_key, _empty_scorecard(*card_key))
        card["attempts"] += 1

        resolved = run.status == "succeeded" and str(key) not in current_keys
        persisted = run.status == "succeeded" and str(key) in current_keys
        unsuccessful = run.status in _UNSUCCESSFUL_STATUSES
        if run.status == "succeeded":
            card["execution_succeeded"] += 1
        if resolved:
            card["resolution_associations"] += 1
        if persisted:
            card["persisted_after_success"] += 1
        if unsuccessful:
            card["unsuccessful_attempts"] += 1

        recent.append(
            {
                "command_id": str(run.id),
                "priority_key": str(key),
                "family": family,
                "decision": str(decision),
                "selected_mode": review.get("selected_mode") or strategy.get("selected_mode"),
                "recommended_mode": review.get("recommended_mode"),
                "effective_mode": str(effective_mode),
                "review_event_id": review.get("event_id"),
                "command_status": run.status,
                "outcome": (
                    "resolution_associated"
                    if resolved
                    else "persisted_after_success"
                    if persisted
                    else "unsuccessful_attempt"
                ),
                "updated_at": run.updated_at,
                "causal_claim": False,
            }
        )

    for card in scorecards.values():
        attempts = int(card["attempts"])
        resolutions = int(card["resolution_associations"])
        card["resolution_rate"] = round(resolutions / attempts, 4) if attempts else 0.0
        card["evidence_strength"] = _evidence_strength(attempts, resolutions)

    ordered_scorecards = sorted(
        scorecards.values(),
        key=lambda item: (
            -int(item["resolution_associations"]),
            -float(item["resolution_rate"]),
            -int(item["attempts"]),
            str(item["family"]),
            str(item["decision"]),
            str(item["effective_mode"]),
        ),
    )

    enriched: list[dict[str, Any]] = []
    active_advisories = 0
    directional_advisories = 0
    for priority in priorities:
        family = _family(priority)
        strategy = priority.get("strategy") or {}
        recommendation = strategy.get("recommendation") or {}
        selected_mode = str(strategy.get("mode") or "baseline")
        recommended_mode = recommendation.get("recommended_mode")
        family_cards = [card for card in ordered_scorecards if card["family"] == family]
        decision_evidence = {
            "keep_selected": _choice_score(
                ordered_scorecards,
                family=family,
                decision="keep_selected",
                effective_mode=selected_mode,
            ),
            "use_recommended": _choice_score(
                ordered_scorecards,
                family=family,
                decision="use_recommended",
                effective_mode=(str(recommended_mode) if recommended_mode else None),
            ),
        }
        review_outcomes = {
            "family": family,
            "total_reviewed_attempts": sum(int(card["attempts"]) for card in family_cards),
            "resolution_associations": sum(
                int(card["resolution_associations"]) for card in family_cards
            ),
            "decision_evidence": decision_evidence,
            "causal_claim": False,
            "interpretation": (
                "Owner strategy-decision scorecards describe recorded associations between "
                "review choices and later priority state; they do not prove that the review "
                "choice caused the outcome."
            ),
        }
        with_outcomes = {**priority, "strategy_review_outcomes": review_outcomes}
        advisory = decision_advisory(with_outcomes)
        if advisory["active"]:
            active_advisories += 1
        if advisory["signal"] in {"keep_selected", "use_recommended"}:
            directional_advisories += 1
        enriched.append({**with_outcomes, "strategy_decision_advisory": advisory})

    calibration = build_executive_advisory_calibration(
        session,
        organization_id,
        enriched,
    )
    confidence = build_executive_advisory_confidence_guardrails(calibration["priorities"])
    refreshed_reviews = build_executive_strategy_reviews(
        session,
        organization_id,
        confidence["priorities"],
    )
    return {
        "priorities": refreshed_reviews["priorities"],
        "summary": {
            "reviewed_attempts": sum(int(card["attempts"]) for card in scorecards.values()),
            "resolution_associations": sum(
                int(card["resolution_associations"]) for card in scorecards.values()
            ),
            "persisted_after_success": sum(
                int(card["persisted_after_success"]) for card in scorecards.values()
            ),
            "unsuccessful_attempts": sum(
                int(card["unsuccessful_attempts"]) for card in scorecards.values()
            ),
            "scored_families": len({card["family"] for card in scorecards.values()}),
            "active_advisories": active_advisories,
            "directional_advisories": directional_advisories,
            "advisory_calibration": calibration["summary"],
            "advisory_calibration_scorecards": calibration["scorecards"],
            "advisory_calibration_history": calibration["recent"],
            "advisory_confidence_guardrails": confidence["summary"],
            "post_advisory_review": refreshed_reviews["summary"],
        },
        "scorecards": ordered_scorecards[:12],
        "recent": recent[:12],
    }
