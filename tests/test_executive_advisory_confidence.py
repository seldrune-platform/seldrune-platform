from backend.app.services.executive_advisory_confidence import advisory_confidence_guardrail
from tests.test_autonomous_execution import register_owner
from tests.test_executive_advisory_calibration import (
    _build_directional_evidence,
    _review_keep_selected,
)
from tests.test_executive_brief import _blocked_project, _project_priority
from tests.test_executive_decision_advisory import (
    _execute_priority,
    _resolve_project,
    _review_use_recommended,
)

pytest_plugins = ["tests.test_autonomous_execution"]


def _priority(
    *,
    base_confidence: str = "medium",
    aligned_attempts: int = 0,
    aligned_rate: float = 0.0,
    diverged_attempts: int = 0,
    diverged_rate: float = 0.0,
) -> dict:
    return {
        "strategy_decision_advisory": {
            "signal": "use_recommended",
            "confidence": base_confidence,
            "owner_decision_required": True,
        },
        "decision_advisory_calibration": {
            "sample_strength": (
                "medium" if aligned_attempts + diverged_attempts >= 2 else "low"
            ),
            "current_signal_aligned": {
                "attempts": aligned_attempts,
                "resolution_rate": aligned_rate,
            },
            "current_signal_diverged": {
                "attempts": diverged_attempts,
                "resolution_rate": diverged_rate,
            },
        },
    }


def test_uncalibrated_directional_advisory_keeps_base_confidence() -> None:
    guardrail = advisory_confidence_guardrail(_priority())
    assert guardrail["status"] == "uncalibrated"
    assert guardrail["base_confidence"] == "medium"
    assert guardrail["calibrated_confidence"] == "medium"
    assert guardrail["confidence_changed"] is False
    assert guardrail["auto_applied"] is False
    assert guardrail["causal_claim"] is False


def test_limited_calibration_can_only_reduce_confidence() -> None:
    guardrail = advisory_confidence_guardrail(
        _priority(aligned_attempts=1, aligned_rate=1.0)
    )
    assert guardrail["status"] == "limited_sample"
    assert guardrail["base_confidence"] == "medium"
    assert guardrail["calibrated_confidence"] == "low"
    assert guardrail["confidence_changed"] is True


def test_consistent_two_sided_calibration_retains_confidence() -> None:
    guardrail = advisory_confidence_guardrail(
        _priority(
            base_confidence="high",
            aligned_attempts=2,
            aligned_rate=0.75,
            diverged_attempts=2,
            diverged_rate=0.25,
        )
    )
    assert guardrail["status"] == "historically_consistent"
    assert guardrail["calibrated_confidence"] == "high"
    assert guardrail["confidence_changed"] is False
    assert guardrail["resolution_rate_delta"] == 0.5


def test_countervailing_calibration_downgrades_without_changing_signal() -> None:
    guardrail = advisory_confidence_guardrail(
        _priority(
            base_confidence="high",
            aligned_attempts=1,
            aligned_rate=0.0,
            diverged_attempts=1,
            diverged_rate=1.0,
        )
    )
    assert guardrail["signal"] == "use_recommended"
    assert guardrail["status"] == "historically_countervailing"
    assert guardrail["base_confidence"] == "high"
    assert guardrail["calibrated_confidence"] == "medium"
    assert guardrail["confidence_changed"] is True
    assert guardrail["resolution_rate_delta"] == -1.0


def test_countervailing_history_is_frozen_into_future_owner_review(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    _build_directional_evidence(client, base, headers)

    aligned_project = _blocked_project(
        client,
        base,
        headers,
        name="Confidence Aligned Epsilon",
        slug="confidence-aligned-epsilon",
    )
    aligned_priority = _project_priority(client, base, headers, aligned_project["id"])
    assert aligned_priority["strategy_decision_advisory"]["signal"] == "use_recommended"
    _review_use_recommended(client, base, headers, aligned_priority)
    aligned_current = _project_priority(client, base, headers, aligned_project["id"])
    _execute_priority(client, base, headers, aligned_current)

    diverged_project = _blocked_project(
        client,
        base,
        headers,
        name="Confidence Diverged Zeta",
        slug="confidence-diverged-zeta",
    )
    diverged_priority = _project_priority(client, base, headers, diverged_project["id"])
    assert diverged_priority["strategy_decision_advisory"]["signal"] == "use_recommended"
    _review_keep_selected(client, base, headers, diverged_priority)
    diverged_current = _project_priority(client, base, headers, diverged_project["id"])
    _execute_priority(client, base, headers, diverged_current)
    _resolve_project(client, base, headers, diverged_project["id"])

    future = _blocked_project(
        client,
        base,
        headers,
        name="Confidence Decision Eta",
        slug="confidence-decision-eta",
    )
    priority = _project_priority(client, base, headers, future["id"])
    advisory = priority["strategy_decision_advisory"]
    guardrail = advisory["confidence_calibration"]
    assert advisory["signal"] == "use_recommended"
    assert advisory["confidence"] == "high"
    assert guardrail["status"] == "historically_countervailing"
    assert guardrail["base_confidence"] == "high"
    assert guardrail["calibrated_confidence"] == "medium"
    assert guardrail["confidence_changed"] is True
    assert guardrail["aligned_attempts"] == 1
    assert guardrail["diverged_attempts"] == 1
    assert guardrail["aligned_resolution_rate"] == 0.0
    assert guardrail["diverged_resolution_rate"] == 1.0
    assert guardrail["resolution_rate_delta"] == -1.0
    assert guardrail["auto_applied"] is False
    assert guardrail["causal_claim"] is False

    reviewed = client.post(
        f"{base}/executive-brief/strategy-reviews/{priority['key']}",
        headers=headers,
        json={
            "decision": "use_recommended",
            "reason": "Owner chooses the recommendation despite countervailing calibration history.",
        },
    )
    assert reviewed.status_code == 200
    snapshot = reviewed.json()["decision_advisory_snapshot"]
    frozen = snapshot["confidence_calibration"]
    assert frozen["status"] == "historically_countervailing"
    assert frozen["base_confidence"] == "high"
    assert frozen["calibrated_confidence"] == "medium"
    assert frozen["confidence_changed"] is True
    assert frozen["causal_claim"] is False

    brief = client.get(f"{base}/executive-brief", headers=headers)
    assert brief.status_code == 200
    summary = brief.json()["strategy_review_outcomes"]["advisory_confidence_guardrails"]
    assert summary["directional_advisories"] >= 1
    assert summary["confidence_downgrades"] >= 1
    assert summary["causal_claim"] is False
