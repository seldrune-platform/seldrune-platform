from tests.test_autonomous_execution import register_owner
from tests.test_executive_brief import _blocked_project, _project_priority
from tests.test_executive_decision_advisory import (
    _execute_priority,
    _resolve_project,
    _review_use_recommended,
)

pytest_plugins = ["tests.test_autonomous_execution"]


def _build_directional_evidence(client, base: str, headers: dict[str, str]) -> None:
    first = _blocked_project(
        client,
        base,
        headers,
        name="Calibration Evidence Alpha",
        slug="calibration-evidence-alpha",
    )
    first_priority = _project_priority(client, base, headers, first["id"])
    _execute_priority(client, base, headers, first_priority)

    second = _blocked_project(
        client,
        base,
        headers,
        name="Calibration Evidence Beta",
        slug="calibration-evidence-beta",
    )
    second_priority = _project_priority(client, base, headers, second["id"])
    _execute_priority(client, base, headers, second_priority)
    _resolve_project(client, base, headers, second["id"])

    for index, suffix in enumerate(("Gamma", "Delta"), start=1):
        project = _blocked_project(
            client,
            base,
            headers,
            name=f"Calibration Reviewed {suffix}",
            slug=f"calibration-reviewed-{index}",
        )
        priority = _project_priority(client, base, headers, project["id"])
        assert priority["strategy_decision_advisory"]["signal"] in {
            "insufficient_evidence",
            "use_recommended",
        }
        _review_use_recommended(client, base, headers, priority)
        refreshed = _project_priority(client, base, headers, project["id"])
        _execute_priority(client, base, headers, refreshed)
        _resolve_project(client, base, headers, project["id"])


def _review_keep_selected(client, base: str, headers: dict[str, str], priority: dict) -> None:
    response = client.post(
        f"{base}/executive-brief/strategy-reviews/{priority['key']}",
        headers=headers,
        json={
            "decision": "keep_selected",
            "reason": "Retain the selected strategy despite the directional historical signal.",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "keep_selected"
    assert response.json()["decision_matched_directional_signal"] is False


def test_directional_advisory_calibration_tracks_aligned_and_diverged_attempts(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    _build_directional_evidence(client, base, headers)

    aligned_project = _blocked_project(
        client,
        base,
        headers,
        name="Calibration Aligned Epsilon",
        slug="calibration-aligned-epsilon",
    )
    aligned_priority = _project_priority(client, base, headers, aligned_project["id"])
    advisory = aligned_priority["strategy_decision_advisory"]
    assert advisory["signal"] == "use_recommended"
    assert advisory["confidence"] == "medium"
    _review_use_recommended(client, base, headers, aligned_priority)
    aligned_current = _project_priority(client, base, headers, aligned_project["id"])
    _execute_priority(client, base, headers, aligned_current)
    _resolve_project(client, base, headers, aligned_project["id"])

    diverged_project = _blocked_project(
        client,
        base,
        headers,
        name="Calibration Diverged Zeta",
        slug="calibration-diverged-zeta",
    )
    diverged_priority = _project_priority(client, base, headers, diverged_project["id"])
    assert diverged_priority["strategy_decision_advisory"]["signal"] == "use_recommended"
    _review_keep_selected(client, base, headers, diverged_priority)
    diverged_current = _project_priority(client, base, headers, diverged_project["id"])
    _execute_priority(client, base, headers, diverged_current)

    brief = client.get(f"{base}/executive-brief", headers=headers)
    assert brief.status_code == 200
    reviewed = brief.json()["strategy_review_outcomes"]
    calibration = reviewed["advisory_calibration"]
    assert calibration["calibrated_attempts"] == 2
    assert calibration["aligned_attempts"] == 1
    assert calibration["diverged_attempts"] == 1
    assert calibration["aligned_resolution_associations"] == 1
    assert calibration["diverged_resolution_associations"] == 0
    assert calibration["aligned_resolution_rate"] == 1.0
    assert calibration["diverged_resolution_rate"] == 0.0
    assert calibration["sample_strength"] == "medium"
    assert calibration["scored_families"] == 1
    assert calibration["causal_claim"] is False

    scorecards = reviewed["advisory_calibration_scorecards"]
    assert len(scorecards) == 2
    aligned_card = next(item for item in scorecards if item["matched_signal"] is True)
    diverged_card = next(item for item in scorecards if item["matched_signal"] is False)
    assert aligned_card["signal"] == "use_recommended"
    assert aligned_card["resolution_associations"] == 1
    assert aligned_card["resolution_rate"] == 1.0
    assert aligned_card["sample_strength"] == "low"
    assert diverged_card["signal"] == "use_recommended"
    assert diverged_card["persisted_after_success"] == 1
    assert diverged_card["resolution_rate"] == 0.0
    assert diverged_card["causal_claim"] is False

    history = reviewed["advisory_calibration_history"]
    calibrated = [item for item in history if item["advisory_signal"] == "use_recommended"]
    assert len(calibrated) == 2
    assert {item["matched_signal"] for item in calibrated} == {True, False}
    assert {item["outcome"] for item in calibrated} == {
        "resolution_associated",
        "persisted_after_success",
    }
