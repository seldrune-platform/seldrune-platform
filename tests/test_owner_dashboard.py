from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def test_owner_dashboard_and_decision_brief(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Analyze healthcare denial management opportunities"},
    )
    assert created.status_code == 201
    command = created.json()

    dashboard = client.get(
        f"/api/v1/organizations/{organization_id}/owner-dashboard", headers=headers
    )
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["command_counts"]["total"] == 1
    assert body["command_counts"]["awaiting_approval"] == 1
    assert body["execution"]["total_steps"] == 3
    assert body["execution"]["matched_steps"] == 3
    assert body["usage"]["total_tokens"] == 0

    brief = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command['id']}/brief",
        headers=headers,
    )
    assert brief.status_code == 200
    decision = brief.json()
    assert decision["approval_status"] == "awaiting_approval"
    assert decision["readiness"] == "ready"
    assert decision["risks"] == []
    assert decision["usage"]["execution_tokens"] == 0
    assert decision["usage"]["estimated_cost_usd"] == 0
    assert all(step["output"] is None for step in decision["steps"])
    assert decision["recommended_next_action"] == "Review the plan and approve the command"
