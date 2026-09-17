from backend.app.services.executive_strategy_review import strategy_review_fingerprint
from tests.test_autonomous_execution import register_owner
from tests.test_executive_brief import _blocked_project, _project_priority

pytest_plugins = ["tests.test_autonomous_execution"]


def _approve_and_execute(client, base: str, headers: dict[str, str], command_id: str) -> None:
    approved = client.post(
        f"{base}/owner-commands/{command_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    executed = client.post(
        f"{base}/owner-commands/{command_id}/execute",
        headers=headers,
        json={"max_steps": 50},
    )
    assert executed.status_code == 200
    assert executed.json()["run"]["status"] == "succeeded"


def test_strategy_review_gates_command_and_applies_owner_choice(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first_project = _blocked_project(
        client,
        base,
        headers,
        name="Review Evidence Alpha",
        slug="review-evidence-alpha",
    )
    first_priority = _project_priority(client, base, headers, first_project["id"])
    assert first_priority["strategy"]["mode"] == "baseline"
    first_command = client.post(
        f"{base}/executive-brief/actions/{first_priority['key']}",
        headers=headers,
    )
    assert first_command.status_code == 201
    _approve_and_execute(client, base, headers, first_command.json()["id"])

    second_project = _blocked_project(
        client,
        base,
        headers,
        name="Review Evidence Beta",
        slug="review-evidence-beta",
    )
    second_priority = _project_priority(client, base, headers, second_project["id"])
    assert second_priority["strategy"]["mode"] == "baseline"
    second_command = client.post(
        f"{base}/executive-brief/actions/{second_priority['key']}",
        headers=headers,
    )
    assert second_command.status_code == 201
    _approve_and_execute(client, base, headers, second_command.json()["id"])

    unblocked = client.patch(
        f"{base}/projects/{second_project['id']}",
        headers=headers,
        json={"status": "active"},
    )
    assert unblocked.status_code == 200

    third_project = _blocked_project(
        client,
        base,
        headers,
        name="Review Decision Gamma",
        slug="review-decision-gamma",
    )
    third_priority = _project_priority(client, base, headers, third_project["id"])
    strategy = third_priority["strategy"]
    review = third_priority["strategy_review"]
    assert strategy["mode"] == "reuse"
    assert strategy["recommendation"]["recommended_mode"] == "baseline"
    assert strategy["recommendation"]["evidence_strength"] == "medium"
    assert strategy["recommendation"]["attempts"] == 2
    assert strategy["recommendation"]["resolution_associations"] == 1
    assert review["required"] is True
    assert review["current"] is False
    assert review["status"] == "pending"
    assert review["effective_mode"] == "reuse"

    blocked = client.post(
        f"{base}/executive-brief/actions/{third_priority['key']}",
        headers=headers,
    )
    assert blocked.status_code == 409
    assert "requires a current owner review" in blocked.json()["detail"]

    reviewed = client.post(
        f"{base}/executive-brief/strategy-reviews/{third_priority['key']}",
        headers=headers,
        json={
            "decision": "use_recommended",
            "reason": "Baseline has stronger verified comparative evidence for this family.",
        },
    )
    assert reviewed.status_code == 200
    review_body = reviewed.json()
    assert review_body["current"] is True
    assert review_body["status"] == "accepted_recommended"
    assert review_body["selected_mode"] == "reuse"
    assert review_body["recommended_mode"] == "baseline"
    assert review_body["effective_mode"] == "baseline"
    assert review_body["event_id"]

    created = client.post(
        f"{base}/executive-brief/actions/{third_priority['key']}",
        headers=headers,
    )
    assert created.status_code == 201
    command = created.json()
    context = command["context"]["executive_strategy"]
    assert context["selected_mode"] == "reuse"
    assert context["mode"] == "baseline"
    assert context["review"]["current"] is True
    assert context["review"]["decision"] == "use_recommended"
    assert context["review"]["effective_mode"] == "baseline"
    assert context["review"]["evidence_fingerprint"]
    assert context["causal_claim"] is False
    assert "Owner strategy review is current" in command["objective"]

    audit = client.get(
        f"{base}/audit-log",
        headers=headers,
        params={"action": "executive.strategy_reviewed"},
    )
    assert audit.status_code == 200
    event = audit.json()["events"][0]
    assert event["resource_id"] == third_priority["key"]
    assert event["details"]["decision"] == "use_recommended"
    assert event["details"]["chosen_mode"] == "baseline"
    assert event["details"]["causal_claim"] is False


def test_strategy_review_fingerprint_changes_with_evidence() -> None:
    priority = {
        "key": "blocked-project:example",
        "escalation": {"level": 0},
        "strategy": {
            "mode": "reuse",
            "preferred_reference_command_id": "command-a",
            "avoid_reference_command_ids": [],
            "outcome_score": {
                "family": "blocked-project",
                "family_attempts": 2,
                "attempts": 0,
                "resolution_associations": 0,
                "persisted_after_success": 0,
                "unsuccessful_attempts": 0,
                "resolution_rate": 0.0,
                "evidence_strength": "none",
            },
            "recommendation": {
                "recommended_mode": "baseline",
                "basis": "comparative_outcome_evidence",
                "evidence_strength": "medium",
                "attempts": 2,
                "resolution_associations": 1,
                "resolution_rate": 0.5,
            },
        },
    }
    before = strategy_review_fingerprint(priority)
    priority["strategy"]["recommendation"]["attempts"] = 3
    after = strategy_review_fingerprint(priority)
    assert before != after


def test_strategy_review_controls_are_served(client) -> None:
    script = client.get("/console-assets/executive-brief.js")
    assert script.status_code == 200
    assert "/executive-brief/strategy-reviews/" in script.text
    assert "Keep ${strategyLabel(strategy.mode)}" in script.text
    assert "Use ${strategyLabel(recommendation.recommended_mode)}" in script.text
    assert "Pending reviews" in script.text
