from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog
from backend.app.models.orchestration import OrchestrationRun

_TERMINAL_STATUSES = {"succeeded", "partial", "failed", "cancelled"}
_UNSUCCESSFUL_STATUSES = {"partial", "failed", "cancelled"}
_DIRECTIONAL_SIGNALS = {"keep_selected", "use_recommended"}
_REVIEW_ACTION = "executive.strategy_reviewed"
_REVIEW_RESOURCE = "executive_strategy_review"


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


def _sample_strength(attempts: int) -> str:
    if attempts >= 5:
        return "high"
    if attempts >= 2:
        return "medium"
    if attempts >= 1:
        return "low"
    return "none"


def _empty_scorecard(
    family: str,
    signal: str,
    confidence: str,
    matched_signal: bool,
) -> dict[str, Any]:
    return {
        "family": family,
        "signal": signal,
        "advisory_confidence": confidence,
        "matched_signal": matched_signal,
        "attempts": 0,
        "execution_succeeded": 0,
        "resolution_associations": 0,
        "persisted_after_success": 0,
        "unsuccessful_attempts": 0,
        "resolution_rate": 0.0,
        "sample_strength": "none",
        "causal_claim": False,
    }


def _aggregate(cards: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "attempts": 0,
        "execution_succeeded": 0,
        "resolution_associations": 0,
        "persisted_after_success": 0,
        "unsuccessful_attempts": 0,
        "resolution_rate": 0.0,
        "sample_strength": "none",
        "causal_claim": False,
    }
    for card in cards:
        for field in (
            "attempts",
            "execution_succeeded",
            "resolution_associations",
            "persisted_after_success",
            "unsuccessful_attempts",
        ):
            result[field] += int(card.get(field) or 0)
    attempts = int(result["attempts"])
    resolutions = int(result["resolution_associations"])
    result["resolution_rate"] = round(resolutions / attempts, 4) if attempts else 0.0
    result["sample_strength"] = _sample_strength(attempts)
    return result


def build_executive_advisory_calibration(
    session: Session,
    organization_id: UUID,
    priorities: list[dict[str, Any]],
) -> dict[str, Any]:
    current_keys = {str(item.get("key")) for item in priorities if item.get("key")}
    review_events = list(
        session.scalars(
            select(AuditLog).where(
                AuditLog.organization_id == organization_id,
                AuditLog.action == _REVIEW_ACTION,
                AuditLog.resource_type == _REVIEW_RESOURCE,
            )
        )
    )
    events_by_id = {str(event.id): event for event in review_events}
    scorecards: dict[tuple[str, str, str, bool], dict[str, Any]] = {}
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
        key = str(priority.get("key") or "")
        event_id = str(review.get("event_id") or "")
        event = events_by_id.get(event_id)
        if not key or event is None:
            continue

        details = event.details or {}
        snapshot = details.get("decision_advisory_snapshot") or {}
        signal = snapshot.get("signal")
        matched = details.get("decision_matched_directional_signal")
        if signal not in _DIRECTIONAL_SIGNALS or not isinstance(matched, bool):
            continue

        family = _family_from_key(key)
        confidence = str(snapshot.get("confidence") or "none")
        card_key = (family, str(signal), confidence, matched)
        card = scorecards.setdefault(card_key, _empty_scorecard(*card_key))
        card["attempts"] += 1

        resolved = run.status == "succeeded" and key not in current_keys
        persisted = run.status == "succeeded" and key in current_keys
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
                "review_event_id": event_id,
                "priority_key": key,
                "family": family,
                "advisory_signal": str(signal),
                "advisory_confidence": confidence,
                "owner_decision": details.get("decision"),
                "matched_signal": matched,
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
        card["sample_strength"] = _sample_strength(attempts)

    ordered_scorecards = sorted(
        scorecards.values(),
        key=lambda item: (
            str(item["family"]),
            str(item["signal"]),
            str(item["advisory_confidence"]),
            not bool(item["matched_signal"]),
        ),
    )
    aligned_cards = [card for card in ordered_scorecards if card["matched_signal"]]
    diverged_cards = [card for card in ordered_scorecards if not card["matched_signal"]]
    aligned = _aggregate(aligned_cards)
    diverged = _aggregate(diverged_cards)

    enriched: list[dict[str, Any]] = []
    for priority in priorities:
        family = _family(priority)
        advisory = priority.get("strategy_decision_advisory") or {}
        current_signal = advisory.get("signal")
        family_cards = [card for card in ordered_scorecards if card["family"] == family]
        signal_cards = (
            [card for card in family_cards if card["signal"] == current_signal]
            if current_signal in _DIRECTIONAL_SIGNALS
            else []
        )
        family_aligned = _aggregate(
            [card for card in signal_cards if card["matched_signal"]]
        )
        family_diverged = _aggregate(
            [card for card in signal_cards if not card["matched_signal"]]
        )
        enriched.append(
            {
                **priority,
                "decision_advisory_calibration": {
                    "family": family,
                    "current_directional_signal": (
                        current_signal if current_signal in _DIRECTIONAL_SIGNALS else None
                    ),
                    "calibrated_attempts": sum(
                        int(card["attempts"]) for card in family_cards
                    ),
                    "current_signal_aligned": family_aligned,
                    "current_signal_diverged": family_diverged,
                    "causal_claim": False,
                    "auto_applied": False,
                    "interpretation": (
                        "Calibration summarizes later outcome associations for governed attempts "
                        "that followed or diverged from previously recorded directional advisory "
                        "signals. It does not score the owner, prove causation, or auto-apply a "
                        "future strategy."
                    ),
                },
            }
        )

    return {
        "priorities": enriched,
        "summary": {
            "calibrated_attempts": int(aligned["attempts"]) + int(diverged["attempts"]),
            "aligned_attempts": aligned["attempts"],
            "diverged_attempts": diverged["attempts"],
            "aligned_resolution_associations": aligned["resolution_associations"],
            "diverged_resolution_associations": diverged["resolution_associations"],
            "aligned_resolution_rate": aligned["resolution_rate"],
            "diverged_resolution_rate": diverged["resolution_rate"],
            "sample_strength": _sample_strength(
                int(aligned["attempts"]) + int(diverged["attempts"])
            ),
            "scored_families": len({card["family"] for card in ordered_scorecards}),
            "causal_claim": False,
        },
        "scorecards": ordered_scorecards[:16],
        "recent": recent[:16],
    }
