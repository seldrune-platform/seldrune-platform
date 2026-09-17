from __future__ import annotations

from collections import Counter
from typing import Any

_DIRECTIONAL_SIGNALS = {"keep_selected", "use_recommended"}
_CONFIDENCE_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
_CONFIDENCE_BY_RANK = {value: key for key, value in _CONFIDENCE_RANK.items()}
_MIN_RATE_DELTA = 0.15


def _score(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _downgrade(confidence: str) -> str:
    rank = _CONFIDENCE_RANK.get(confidence, 0)
    return _CONFIDENCE_BY_RANK[max(0, rank - 1)]


def advisory_confidence_guardrail(priority: dict[str, Any]) -> dict[str, Any]:
    advisory = _score(priority.get("strategy_decision_advisory"))
    calibration = _score(priority.get("decision_advisory_calibration"))
    signal = advisory.get("signal")
    base_confidence = str(advisory.get("confidence") or "none")
    aligned = _score(calibration.get("current_signal_aligned"))
    diverged = _score(calibration.get("current_signal_diverged"))
    aligned_attempts = int(aligned.get("attempts") or 0)
    diverged_attempts = int(diverged.get("attempts") or 0)
    total_attempts = aligned_attempts + diverged_attempts
    aligned_rate = float(aligned.get("resolution_rate") or 0.0)
    diverged_rate = float(diverged.get("resolution_rate") or 0.0)
    rate_delta = round(aligned_rate - diverged_rate, 4)

    calibrated_confidence = base_confidence
    status = "not_applicable"
    basis = "advisory_is_not_directional"

    if signal in _DIRECTIONAL_SIGNALS:
        if total_attempts == 0:
            status = "uncalibrated"
            basis = "no_directional_calibration_history"
        elif total_attempts < 2:
            status = "limited_sample"
            basis = "directional_calibration_sample_below_two_attempts"
            calibrated_confidence = _downgrade(base_confidence)
        elif aligned_attempts == 0 or diverged_attempts == 0:
            status = "one_sided_sample"
            basis = "calibration_history_does_not_cover_both_owner_choices"
            calibrated_confidence = _downgrade(base_confidence)
        elif rate_delta >= _MIN_RATE_DELTA:
            status = "historically_consistent"
            basis = "aligned_attempts_have_higher_resolution_association"
        elif rate_delta <= -_MIN_RATE_DELTA:
            status = "historically_countervailing"
            basis = "diverged_attempts_have_higher_resolution_association"
            calibrated_confidence = _downgrade(base_confidence)
        else:
            status = "historically_mixed"
            basis = "aligned_and_diverged_resolution_rates_are_not_materially_different"
            calibrated_confidence = _downgrade(base_confidence)

    return {
        "status": status,
        "basis": basis,
        "signal": signal if signal in _DIRECTIONAL_SIGNALS else None,
        "base_confidence": base_confidence,
        "calibrated_confidence": calibrated_confidence,
        "confidence_changed": calibrated_confidence != base_confidence,
        "calibrated_attempts": total_attempts,
        "aligned_attempts": aligned_attempts,
        "diverged_attempts": diverged_attempts,
        "aligned_resolution_rate": aligned_rate,
        "diverged_resolution_rate": diverged_rate,
        "resolution_rate_delta": rate_delta,
        "sample_strength": str(calibration.get("sample_strength") or "none"),
        "owner_decision_required": bool(advisory.get("owner_decision_required")),
        "auto_applied": False,
        "causal_claim": False,
        "interpretation": (
            "Calibration can retain or reduce the displayed advisory confidence, but never "
            "strengthen the underlying advisory, choose a strategy, or establish that following "
            "or diverging from an advisory caused the later outcome."
        ),
    }


def build_executive_advisory_confidence_guardrails(
    priorities: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    downgraded = 0
    directional = 0

    for priority in priorities:
        advisory = _score(priority.get("strategy_decision_advisory"))
        guardrail = advisory_confidence_guardrail(priority)
        statuses[guardrail["status"]] += 1
        if guardrail["signal"] in _DIRECTIONAL_SIGNALS:
            directional += 1
        if guardrail["confidence_changed"]:
            downgraded += 1
        enriched.append(
            {
                **priority,
                "strategy_decision_advisory": {
                    **advisory,
                    "confidence_calibration": guardrail,
                },
            }
        )

    return {
        "priorities": enriched,
        "summary": {
            "directional_advisories": directional,
            "confidence_downgrades": downgraded,
            "statuses": dict(sorted(statuses.items())),
            "auto_applied": False,
            "causal_claim": False,
        },
    }
