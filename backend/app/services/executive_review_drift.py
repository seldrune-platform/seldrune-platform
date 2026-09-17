from __future__ import annotations

from collections import Counter
from typing import Any


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _calibrated_confidence(advisory: dict[str, Any]) -> str:
    calibration = _mapping(advisory.get("confidence_calibration"))
    return str(
        calibration.get("calibrated_confidence")
        or advisory.get("confidence")
        or "none"
    )


def explain_review_drift(priority: dict[str, Any]) -> dict[str, Any]:
    review = _mapping(priority.get("strategy_review"))
    strategy = _mapping(priority.get("strategy"))
    recommendation = _mapping(strategy.get("recommendation"))
    current_advisory = _mapping(priority.get("strategy_decision_advisory"))
    reviewed_advisory = _mapping(review.get("decision_advisory_snapshot"))

    stale = review.get("status") == "stale"
    stale_reason = review.get("stale_reason")
    reviewed_signal = reviewed_advisory.get("signal")
    current_signal = current_advisory.get("signal")
    reviewed_confidence = _calibrated_confidence(reviewed_advisory)
    current_confidence = _calibrated_confidence(current_advisory)

    changes: list[str] = []
    if stale_reason in {
        "strategy_evidence_changed",
        "strategy_and_material_advisory_evidence_changed",
    }:
        changes.append("strategy_evidence")
    if review.get("selected_mode") != strategy.get("mode"):
        changes.append("selected_mode")
    if review.get("recommended_mode") != recommendation.get("recommended_mode"):
        changes.append("recommended_mode")
    if review.get("advisory_material_current") is False:
        if reviewed_signal != current_signal:
            changes.append("advisory_signal")
        if reviewed_confidence != current_confidence:
            changes.append("advisory_confidence")

    return {
        "active": stale,
        "stale_reason": stale_reason if stale else None,
        "changes": changes if stale else [],
        "reviewed": {
            "selected_mode": review.get("selected_mode"),
            "recommended_mode": review.get("recommended_mode"),
            "advisory_signal": reviewed_signal,
            "advisory_confidence": reviewed_confidence,
        },
        "current": {
            "selected_mode": strategy.get("mode"),
            "recommended_mode": recommendation.get("recommended_mode"),
            "advisory_signal": current_signal,
            "advisory_confidence": current_confidence,
        },
        "owner_rereview_required": bool(stale and review.get("required")),
        "auto_applied": False,
        "causal_claim": False,
        "interpretation": (
            "This comparison explains which reviewed evidence dimensions changed. It does not "
            "grade the prior owner decision, auto-select a strategy, or establish that any "
            "historical choice caused a later organizational outcome."
        ),
    }


def build_executive_review_drift_explanations(
    priorities: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    change_counts: Counter[str] = Counter()
    stale_reviews = 0
    explained = 0

    for priority in priorities:
        explanation = explain_review_drift(priority)
        if explanation["active"]:
            stale_reviews += 1
            if explanation["changes"]:
                explained += 1
            change_counts.update(explanation["changes"])
        review = _mapping(priority.get("strategy_review"))
        enriched.append(
            {
                **priority,
                "strategy_review": {
                    **review,
                    "drift_explanation": explanation,
                },
            }
        )

    return {
        "priorities": enriched,
        "summary": {
            "stale_reviews": stale_reviews,
            "explained_stale_reviews": explained,
            "change_counts": dict(sorted(change_counts.items())),
            "auto_applied": False,
            "causal_claim": False,
        },
    }
