from backend.app.services.executive_strategy import evaluate_executive_strategies


def _priority(
    *,
    preferred: bool = True,
    escalation_level: int = 0,
    modes: dict | None = None,
) -> dict:
    memory = {
        "confidence": "medium",
        "preferred_pattern": {"command_id": "prior-resolution"} if preferred else None,
        "avoid_patterns": [],
    }
    return {
        "key": "blocked-project:current",
        "action": {"kind": "owner_command"},
        "escalation": {"level": escalation_level},
        "outcome_memory": memory,
        "strategy_outcomes": {
            "family": "blocked-project",
            "total_attempts": sum(int(item.get("attempts", 0)) for item in (modes or {}).values()),
            "modes": modes or {},
        },
    }


def _score(
    *,
    attempts: int,
    resolutions: int,
    resolution_rate: float,
    strength: str,
    unsuccessful: int = 0,
) -> dict:
    return {
        "attempts": attempts,
        "resolution_associations": resolutions,
        "resolution_rate": resolution_rate,
        "evidence_strength": strength,
        "unsuccessful_attempts": unsuccessful,
        "persisted_after_success": 0,
    }


def test_recommends_stronger_comparative_mode_without_auto_applying() -> None:
    priority = _priority(
        modes={
            "baseline": _score(
                attempts=2,
                resolutions=2,
                resolution_rate=1.0,
                strength="medium",
            ),
        }
    )

    result = evaluate_executive_strategies([priority])
    strategy = result["priorities"][0]["strategy"]
    recommendation = strategy["recommendation"]

    assert strategy["mode"] == "reuse"
    assert recommendation["selected_mode"] == "reuse"
    assert recommendation["recommended_mode"] == "baseline"
    assert recommendation["basis"] == "comparative_outcome_evidence"
    assert recommendation["evidence_strength"] == "medium"
    assert recommendation["attempts"] == 2
    assert recommendation["resolution_associations"] == 2
    assert recommendation["resolution_rate"] == 1.0
    assert recommendation["auto_applied"] is False
    assert recommendation["owner_review_required"] is True
    assert recommendation["causal_claim"] is False
    assert result["summary"]["comparative_recommendations"] == 1


def test_keeps_selected_mode_when_comparative_evidence_is_not_better() -> None:
    priority = _priority(
        modes={
            "reuse": _score(
                attempts=3,
                resolutions=2,
                resolution_rate=0.6667,
                strength="high",
            ),
            "baseline": _score(
                attempts=2,
                resolutions=1,
                resolution_rate=0.5,
                strength="medium",
            ),
        }
    )

    result = evaluate_executive_strategies([priority])
    recommendation = result["priorities"][0]["strategy"]["recommendation"]

    assert recommendation["recommended_mode"] is None
    assert recommendation["basis"] == "selected_mode_supported"
    assert recommendation["auto_applied"] is False
    assert result["summary"]["comparative_recommendations"] == 0


def test_escalated_recovery_is_not_overridden_by_historical_scores() -> None:
    priority = _priority(
        escalation_level=2,
        modes={
            "baseline": _score(
                attempts=4,
                resolutions=4,
                resolution_rate=1.0,
                strength="high",
            ),
        },
    )

    result = evaluate_executive_strategies([priority])
    strategy = result["priorities"][0]["strategy"]
    recommendation = strategy["recommendation"]

    assert strategy["mode"] == "recover"
    assert recommendation["recommended_mode"] is None
    assert recommendation["basis"] == "escalation_control"
    assert recommendation["auto_applied"] is False
    assert recommendation["owner_review_required"] is True
