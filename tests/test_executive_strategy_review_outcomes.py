from tests.test_autonomous_execution import register_owner
from tests.test_executive_brief import _blocked_project, _project_priority
from tests.test_executive_strategy_review import _approve_and_execute

pytest_plugins = ["tests.test_autonomous_execution"]


def _create_execute_and_optionally_resolve(
    client,
    base: str,
    headers: dict[str, str],
    priority: dict,
    *,
    project_id: str,
    resolve: bool,
) -> None:
    created = client.post(
        f"{base}/executive-brief/actions/{priority['key']}",
        headers=headers,
    )
    assert created.status_code == 201
    _approve_and_execute(client, base, headers, created.json()["id"])
    if resolve:
        updated = client.patch(
            f"{base}/projects/{project_id}",
            headers=headers,
            json={"status": "active"},
        )
        assert updated.status_code == 200


def test_reviewed_strategy_outcomes_inform_future_owner_decisions(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first_project = _blocked_project(
        client,
        base,
        headers,
        name="Decision Learning Alpha",
        slug="decision-learning-alpha",
    )
    first_priority = _project_priority(client, base, headers, first_project["id"])
    assert first_priority["strategy"]["mode"] == "baseline"
    _create_execute_and_optionally_resolve(
        client,
        base,
        headers,
        first_priority,
        project_id=first_project["id"],
        resolve=False,
    )

    second_project = _blocked_project(
        client,
        base,
        headers,
        name="Decision Learning Beta",
        slug="decision-learning-beta",
    )
    second_priority = _project_priority(client, base, headers, second_project["id"])
    assert second_priority["strategy"]["mode"] == "baseline"
    _create_execute_and_optionally_resolve(
        client,
        base,
        headers,
        second_priority,
        project_id=second_project["id"],
        resolve=True,
    )

    reviewed_project = _blocked_project(
        client,
        base,
        headers,
        name="Decision Learning Gamma",
        slug="decision-learning-gamma",
    )
    reviewed_priority = _project_priority(client, base, headers, reviewed_project["id"])
    assert reviewed_priority["strategy"]["mode"] == "reuse"
    assert reviewed_priority["strategy"]["recommendation"]["recommended_mode"] == "baseline"

    review = client.post(
        f"{base}/executive-brief/strategy-reviews/{reviewed_priority['key']}",
        headers=headers,
        json={
            "decision": "use_recommended",
            "reason": "Use the stronger baseline evidence for this governed attempt.",
        },
    )
    assert review.status_code == 200
    assert review.json()["effective_mode"] == "baseline"

    refreshed_reviewed = _project_priority(
        client,
        base,
        headers,
        reviewed_project["id"],
    )
    _create_execute_and_optionally_resolve(
        client,
        base,
        headers,
        refreshed_reviewed,
        project_id=reviewed_project["id"],
        resolve=True,
    )

    future_project = _blocked_project(
        client,
        base,
        headers,
        name="Decision Learning Delta",
        slug="decision-learning-delta",
    )
    future_priority = _project_priority(client, base, headers, future_project["id"])
    learned = future_priority["strategy_review_outcomes"]
    assert learned["family"] == "blocked-project"
    assert learned["total_reviewed_attempts"] == 1
    assert learned["resolution_associations"] == 1
    assert learned["causal_claim"] is False

    recommended_evidence = learned["decision_evidence"]["use_recommended"]
    assert recommended_evidence["decision"] == "use_recommended"
    assert recommended_evidence["effective_mode"] == "baseline"
    assert recommended_evidence["attempts"] == 1
    assert recommended_evidence["resolution_associations"] == 1
    assert recommended_evidence["resolution_rate"] == 1.0
    assert recommended_evidence["evidence_strength"] == "low"
    assert recommended_evidence["causal_claim"] is False

    brief = client.get(f"{base}/executive-brief", headers=headers)
    assert brief.status_code == 200
    payload = brief.json()
    summary = payload["strategy_review_outcomes"]
    assert summary["reviewed_attempts"] == 1
    assert summary["resolution_associations"] == 1
    assert summary["persisted_after_success"] == 0
    assert summary["unsuccessful_attempts"] == 0
    assert summary["scored_families"] == 1
    assert payload["strategy_review_scorecards"][0]["decision"] == "use_recommended"
    assert payload["strategy_review_outcome_history"][0]["outcome"] == "resolution_associated"
    assert payload["strategy_review_outcome_history"][0]["causal_claim"] is False

    future_strategy = future_priority["strategy"]
    recommendation = future_strategy["recommendation"]
    assert recommendation["recommended_mode"] == "baseline"
    next_review = client.post(
        f"{base}/executive-brief/strategy-reviews/{future_priority['key']}",
        headers=headers,
        json={
            "decision": "keep_selected",
            "reason": "Current conditions justify retaining the selected strategy.",
        },
    )
    assert next_review.status_code == 200

    current_future = _project_priority(client, base, headers, future_project["id"])
    created = client.post(
        f"{base}/executive-brief/actions/{current_future['key']}",
        headers=headers,
    )
    assert created.status_code == 201
    context = created.json()["context"]["executive_strategy"]
    review_outcomes = context["review_outcomes"]
    assert review_outcomes["total_reviewed_attempts"] == 1
    assert review_outcomes["resolution_associations"] == 1
    assert review_outcomes["decision_evidence"]["use_recommended"]["attempts"] == 1
    assert review_outcomes["causal_claim"] is False
    assert "Historical owner review outcomes are available" in created.json()["objective"]
