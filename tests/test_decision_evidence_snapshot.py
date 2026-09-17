from backend.app.services.executive_strategy_review import decision_advisory_snapshot
from tests.test_autonomous_execution import register_owner
from tests.test_executive_brief import _blocked_project, _project_priority
from tests.test_executive_decision_advisory import (
    _execute_priority,
    _resolve_project,
    _review_use_recommended,
)

pytest_plugins = ["tests.test_autonomous_execution"]


def test_decision_advisory_snapshot_normalizes_evidence() -> None:
    priority = {
        "strategy_decision_advisory": {
            "active": True,
            "signal": "use_recommended",
            "basis": "reviewed_recommended_choice_supported",
            "confidence": "medium",
            "resolution_rate_delta": 1.0,
            "selected_mode": "reuse",
            "recommended_mode": "baseline",
            "keep_selected_evidence": {
                "decision": "keep_selected",
                "effective_mode": "reuse",
            },
            "use_recommended_evidence": {
                "decision": "use_recommended",
                "effective_mode": "baseline",
                "attempts": 2,
                "resolution_associations": 2,
                "resolution_rate": 1.0,
                "evidence_strength": "medium",
            },
            "owner_decision_required": True,
        }
    }
    snapshot = decision_advisory_snapshot(priority)
    assert snapshot["signal"] == "use_recommended"
    assert snapshot["confidence"] == "medium"
    assert snapshot["use_recommended_evidence"]["attempts"] == 2
    assert snapshot["use_recommended_evidence"]["resolution_associations"] == 2
    assert snapshot["keep_selected_evidence"]["attempts"] == 0
    assert snapshot["auto_applied"] is False
    assert snapshot["causal_claim"] is False


def test_directional_advisory_is_frozen_into_owner_review_audit(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first = _blocked_project(
        client,
        base,
        headers,
        name="Snapshot Evidence Alpha",
        slug="snapshot-evidence-alpha",
    )
    first_priority = _project_priority(client, base, headers, first["id"])
    _execute_priority(client, base, headers, first_priority)

    second = _blocked_project(
        client,
        base,
        headers,
        name="Snapshot Evidence Beta",
        slug="snapshot-evidence-beta",
    )
    second_priority = _project_priority(client, base, headers, second["id"])
    _execute_priority(client, base, headers, second_priority)
    _resolve_project(client, base, headers, second["id"])

    for index, suffix in enumerate(("Gamma", "Delta"), start=1):
        project = _blocked_project(
            client,
            base,
            headers,
            name=f"Snapshot Reviewed {suffix}",
            slug=f"snapshot-reviewed-{index}",
        )
        priority = _project_priority(client, base, headers, project["id"])
        assert priority["strategy"]["recommendation"]["recommended_mode"] == "baseline"
        _review_use_recommended(client, base, headers, priority)
        refreshed = _project_priority(client, base, headers, project["id"])
        _execute_priority(client, base, headers, refreshed)
        _resolve_project(client, base, headers, project["id"])

    future = _blocked_project(
        client,
        base,
        headers,
        name="Snapshot Decision Epsilon",
        slug="snapshot-decision-epsilon",
    )
    priority = _project_priority(client, base, headers, future["id"])
    advisory = priority["strategy_decision_advisory"]
    assert advisory["signal"] == "use_recommended"
    assert advisory["confidence"] == "medium"
    assert advisory["use_recommended_evidence"]["attempts"] == 2

    reviewed = client.post(
        f"{base}/executive-brief/strategy-reviews/{priority['key']}",
        headers=headers,
        json={
            "decision": "use_recommended",
            "reason": "Use the directional historical evidence while retaining owner control.",
        },
    )
    assert reviewed.status_code == 200
    review = reviewed.json()
    snapshot = review["decision_advisory_snapshot"]
    assert snapshot["signal"] == "use_recommended"
    assert snapshot["confidence"] == "medium"
    assert snapshot["use_recommended_evidence"]["attempts"] == 2
    assert snapshot["use_recommended_evidence"]["resolution_associations"] == 2
    assert snapshot["auto_applied"] is False
    assert snapshot["causal_claim"] is False
    assert review["decision_matched_directional_signal"] is True

    audit = client.get(
        f"{base}/audit-log",
        headers=headers,
        params={"action": "executive.strategy_reviewed"},
    )
    assert audit.status_code == 200
    event = audit.json()["events"][0]
    details = event["details"]
    assert details["priority_key"] == priority["key"]
    assert details["decision"] == "use_recommended"
    assert details["decision_matched_directional_signal"] is True
    audit_snapshot = details["decision_advisory_snapshot"]
    assert audit_snapshot["signal"] == "use_recommended"
    assert audit_snapshot["basis"] == "reviewed_recommended_choice_supported"
    assert audit_snapshot["confidence"] == "medium"
    assert audit_snapshot["use_recommended_evidence"]["attempts"] == 2
    assert audit_snapshot["use_recommended_evidence"]["resolution_rate"] == 1.0
    assert audit_snapshot["causal_claim"] is False
