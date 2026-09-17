from __future__ import annotations

from collections import Counter
from typing import Any

_STRENGTH_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
_DIRECTIONAL_MIN_STRENGTH = 2
_MIN_RATE_DELTA = 0.15


def _scorecard(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _evidence_payload(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": score.get("decision"),
        "effective_mode": score.get("effective_mode"),
        "attempts": int(score.get("attempts") or 0),
        "resolution_associations": int(score.get("resolution_associations") or 0),
        "persisted_after_success": int(score.get("persisted_after_success") or 0),
        "unsuccessful_attempts": int(score.get("unsuccessful_attempts") or 0),
        "resolution_rate": float(score.get("resolution_rate") or 0.0),
        "evidence_strength": str(score.get("evidence_strength") or "none"),
        "causal_claim": False,
    }


def _eligible(score: dict[str, Any]) -> bool:
    strength = str(score.get("evidence_strength") or "none")
    return (
        int(score.get("attempts") or 0) >= 2
        and int(score.get("resolution_associations") or 0) >= 1
        and _STRENGTH_RANK.get(strength, 0) >= _DIRECTIONAL_MIN_STRENGTH
    )


def _empty_advisory(
    *,
    selected_mode: str,
    recommended_mode: str | None,
    basis: str,
    keep: dict[str, Any],
    use: dict[str, Any],
) -> dict[str, Any]:
    return {
        "active": bool(recommended_mode),
        "signal": "insufficient_evidence" if recommended_mode else "not_applicable",
        "basis": basis,
        "selected_mode": selected_mode,
        "recommended_mode": recommended_mode,
        "confidence": "none",
        "resolution_rate_delta": 0.0,
        "keep_selected_evidence": _evidence_payload(keep),
        "use_recommended_evidence": _evidence_payload(use),
        "owner_decision_required": bool(recommended_mode),
        "auto_applied": False,
        "causal_claim": False,
        "interpretation": (
            "Historical owner-review outcomes are associative evidence only. They do not prove "
            "that keeping or using a recommendation caused the later organizational outcome."
        ),
    }


def decision_advisory(priority: dict[str, Any]) -> dict[str, Any]:
    strategy = priority.get("strategy") or {}
    selected_mode = str(strategy.get("mode") or "baseline")
    recommendation = strategy.get("recommendation") or {}
    recommended_mode = recommendation.get("recommended_mode")
    outcomes = priority.get("strategy_review_outcomes") or {}
    evidence = outcomes.get("decision_evidence") or {}
    keep = _scorecard(evidence.get("keep_selected"))
    use = _scorecard(evidence.get("use_recommended"))

    if not recommended_mode:
        return _empty_advisory(
            selected_mode=selected_mode,
            recommended_mode=None,
            basis="no_comparative_recommendation",
            keep=keep,
            use=use,
        )

    keep_ok = _eligible(keep)
    use_ok = _eligible(use)
    if not keep_ok and not use_ok:
        return _empty_advisory(
            selected_mode=selected_mode,
            recommended_mode=str(recommended_mode),
            basis="insufficient_review_outcome_evidence",
            keep=keep,
            use=use,
        )

    keep_rate = float(keep.get("resolution_rate") or 0.0)
    use_rate = float(use.get("resolution_rate") or 0.0)
    delta = round(use_rate - keep_rate, 4)

    if use_ok and not keep_ok:
        signal = "use_recommended"
        confidence = str(use.get("evidence_strength") or "none")
        basis = "reviewed_recommended_choice_supported"
    elif keep_ok and not use_ok:
        signal = "keep_selected"
        confidence = str(keep.get("evidence_strength") or "none")
        basis = "reviewed_selected_choice_supported"
    elif delta >= _MIN_RATE_DELTA:
        signal = "use_recommended"
        confidence = min(
            str(use.get("evidence_strength") or "none"),
            str(keep.get("evidence_strength") or "none"),
            key=lambda value: _STRENGTH_RANK.get(value, 0),
        )
        basis = "comparative_review_outcome_evidence"
    elif delta <= -_MIN_RATE_DELTA:
        signal = "keep_selected"
        confidence = min(
            str(use.get("evidence_strength") or "none"),
            str(keep.get("evidence_strength") or "none"),
            key=lambda value: _STRENGTH_RANK.get(value, 0),
        )
        basis = "comparative_review_outcome_evidence"
    else:
        signal = "mixed"
        confidence = min(
            str(use.get("evidence_strength") or "none"),
            str(keep.get("evidence_strength") or "none"),
            key=lambda value: _STRENGTH_RANK.get(value, 0),
        )
        basis = "review_outcomes_not_materially_different"

    return {
        "active": True,
        "signal": signal,
        "basis": basis,
        "selected_mode": selected_mode,
        "recommended_mode": str(recommended_mode),
        "confidence": confidence,
        "resolution_rate_delta": delta,
        "keep_selected_evidence": _evidence_payload(keep),
        "use_recommended_evidence": _evidence_payload(use),
        "owner_decision_required": True,
        "auto_applied": False,
        "causal_claim": False,
        "interpretation": (
            "The signal summarizes recorded owner-review outcome associations. It does not choose "
            "a strategy, override current evidence, or establish causation."
        ),
    }


def build_executive_decision_advisories(
    priorities: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    signals: Counter[str] = Counter()
    active = 0
    directional = 0

    for priority in priorities:
        advisory = decision_advisory(priority)
        enriched.append({**priority, "strategy_decision_advisory": advisory})
        signals[advisory["signal"]] += 1
        if advisory["active"]:
            active += 1
        if advisory["signal"] in {"keep_selected", "use_recommended"}:
            directional += 1

    return {
        "priorities": enriched,
        "summary": {
            "active_advisories": active,
            "directional_signals": directional,
            "signals": dict(sorted(signals.items())),
        },
    }
