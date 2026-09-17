from backend.app.services.executive_strategy_review import advisory_material_fingerprint
from tests.test_autonomous_execution import register_owner
from tests.test_executive_brief import _blocked_project, _project_priority
from tests.test_executive_decision_advisory import (
    _execute_priority,
    _resolve_project,
    _review_use_recommended,
)

pytest_plugins = ["tests.test_autonomous_execution"]


def test_material_advisory_fingerprint_ignores_nonmaterial_count_changes() -> None:
    priority = {
        "strategy_decision_advisory": {
            "signal": "use_recommended",
            "confidence": "high",
            "confidence_calibration": {
                "calibrated_confidence": "medium",
                "calibrated_attempts": 2,
                "aligned_attempts": 1,
                "diverged_attempts": 1,
            },
        }
    }
    original = advisory_material_fingerprint(priority)

    priority["strategy_decision_advisory"]["confidence_calibration"][
        "calibrated_attempts"
    ] = 8
    priority["strategy_decision_advisory"]["confidence_calibration"][
        "aligned_attempts"
    ] = 5
    assert advisory_material_fingerprint(priority) == original

    priority["strategy_decision_advisory"]["confidence_calibration"][
        "calibrated_confidence"
    ] = "low"
    changed_confidence = advisory_material_fingerprint(priority)
    assert changed_confidence != original

    priority["strategy_decision_advisory"]["signal"] = "keep_selected"
    assert advisory_material_fingerprint(priority) != changed_confidence


def test_material_advisory_drift_requires_fresh_owner_review(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first = _blocked_project(
        client,
        base,
        headers,
        name="Drift Evidence Alpha",
        slug="drift-evidence-alpha",
    )
    first_priority = _project_priority(client, base, headers, first["id"])
    _execute_priority(client, base, headers, first_priority)

    second = _blocked_project(
        client,
        base,
        headers,
        name="Drift Evidence Beta",
        slug="drift-evidence-beta",
    )
    second_priority = _project_priority(client, base, headers, second["id"])
    _execute_priority(client, base, headers, second_priority)
    _resolve_project(client, base, headers, second["id"])

    target = _blocked_project(
        client,
        base,
        headers,
        name="Drift Target Gamma",
        slug="drift-target-gamma",
    )
    target_priority = _project_priority(client, base, headers, target["id"])
    assert target_priority["strategy"]["recommendation"]["recommended_mode"] == "baseline"
    assert target_priority["strategy_decision_advisory"]["signal"] == "insufficient_evidence"

    initial_review = client.post(
        f"{base}/executive-brief/strategy-reviews/{target_priority['key']}",
        headers=headers,
        json={
            "decision": "use_recommended",
            "reason": "Use the current recommendation while evidence remains limited.",
        },
    )
    assert initial_review.status_code == 200
    initial_state = initial_review.json()
    assert initial_state["current"] is True
    assert initial_state["advisory_material_tracked"] is True
    assert initial_state["advisory_material_current"] is True
    initial_material_fingerprint = initial_state["advisory_material_fingerprint"]

    for index, suffix in enumerate(("Delta", "Epsilon"), start=1):
        project = _blocked_project(
            client,
            base,
            headers,
            name=f"Drift Reviewed {suffix}",
            slug=f"drift-reviewed-{index}",
        )
        priority = _project_priority(client, base, headers, project["id"])
        assert priority["strategy"]["recommendation"]["recommended_mode"] == "baseline"
        _review_use_recommended(client, base, headers, priority)
        refreshed = _project_priority(client, base, headers, project["id"])
        _execute_priority(client, base, headers, refreshed)
        _resolve_project(client, base, headers, project["id"])

    drifted = _project_priority(client, base, headers, target["id"])
    advisory = drifted["strategy_decision_advisory"]
    review = drifted["strategy_review"]
    assert advisory["signal"] == "use_recommended"
    assert advisory["confidence"] == "medium"
    assert review["current"] is False
    assert review["status"] == "stale"
    assert review["stale_reason"] == "material_advisory_evidence_changed"
    assert review["advisory_material_tracked"] is True
    assert review["advisory_material_current"] is False
    assert review["advisory_material_fingerprint"] != initial_material_fingerprint

    blocked = client.post(
        f"{base}/executive-brief/actions/{drifted['key']}",
        headers=headers,
    )
    assert blocked.status_code == 409
    assert "current owner review" in blocked.json()["detail"]

    rereview = client.post(
        f"{base}/executive-brief/strategy-reviews/{drifted['key']}",
        headers=headers,
        json={
            "decision": "use_recommended",
            "reason": "Re-review after the advisory evidence materially changed.",
        },
    )
    assert rereview.status_code == 200
    rereview_state = rereview.json()
    assert rereview_state["current"] is True
    assert rereview_state["advisory_material_current"] is True
    assert rereview_state["advisory_material_fingerprint"] != initial_material_fingerprint

    created = client.post(
        f"{base}/executive-brief/actions/{drifted['key']}",
        headers=headers,
    )
    assert created.status_code == 201

    brief = client.get(f"{base}/executive-brief", headers=headers)
    assert brief.status_code == 200
    post_review = brief.json()["strategy_review_outcomes"]["post_advisory_review"]
    assert post_review["material_drift_stale"] == 0
