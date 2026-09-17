from backend.app.services.executive_review_drift import (
    build_executive_review_drift_explanations,
    explain_review_drift,
)


def _stale_priority() -> dict:
    return {
        "strategy": {
            "mode": "reuse",
            "recommendation": {"recommended_mode": "baseline"},
        },
        "strategy_decision_advisory": {
            "signal": "use_recommended",
            "confidence": "medium",
            "confidence_calibration": {"calibrated_confidence": "medium"},
        },
        "strategy_review": {
            "required": True,
            "current": False,
            "status": "stale",
            "stale_reason": "strategy_and_material_advisory_evidence_changed",
            "selected_mode": "reuse",
            "recommended_mode": "baseline",
            "advisory_material_current": False,
            "decision_advisory_snapshot": {
                "signal": "insufficient_evidence",
                "confidence": "none",
                "confidence_calibration": {"calibrated_confidence": "none"},
            },
        },
    }


def test_review_drift_explains_material_and_strategy_changes() -> None:
    explanation = explain_review_drift(_stale_priority())
    assert explanation["active"] is True
    assert explanation["owner_rereview_required"] is True
    assert explanation["stale_reason"] == "strategy_and_material_advisory_evidence_changed"
    assert explanation["changes"] == [
        "strategy_evidence",
        "advisory_signal",
        "advisory_confidence",
    ]
    assert explanation["reviewed"]["advisory_signal"] == "insufficient_evidence"
    assert explanation["reviewed"]["advisory_confidence"] == "none"
    assert explanation["current"]["advisory_signal"] == "use_recommended"
    assert explanation["current"]["advisory_confidence"] == "medium"
    assert explanation["auto_applied"] is False
    assert explanation["causal_claim"] is False


def test_current_review_has_no_active_drift_explanation() -> None:
    priority = _stale_priority()
    priority["strategy_review"] = {
        **priority["strategy_review"],
        "current": True,
        "status": "accepted_recommended",
        "stale_reason": None,
        "advisory_material_current": True,
        "decision_advisory_snapshot": priority["strategy_decision_advisory"],
    }
    explanation = explain_review_drift(priority)
    assert explanation["active"] is False
    assert explanation["changes"] == []
    assert explanation["owner_rereview_required"] is False


def test_review_drift_builder_summarizes_changed_dimensions() -> None:
    stale = _stale_priority()
    current = {
        **_stale_priority(),
        "strategy_review": {
            **_stale_priority()["strategy_review"],
            "current": True,
            "status": "accepted_selected",
            "stale_reason": None,
            "advisory_material_current": True,
        },
    }
    result = build_executive_review_drift_explanations([stale, current])
    assert result["summary"]["stale_reviews"] == 1
    assert result["summary"]["explained_stale_reviews"] == 1
    assert result["summary"]["change_counts"] == {
        "advisory_confidence": 1,
        "advisory_signal": 1,
        "strategy_evidence": 1,
    }
    assert result["priorities"][0]["strategy_review"]["drift_explanation"]["active"]
    assert result["summary"]["auto_applied"] is False
    assert result["summary"]["causal_claim"] is False
