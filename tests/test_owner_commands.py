from tests.test_autonomous_execution import client as _client  # noqa: F401
from tests.test_autonomous_execution import create_agent, register_owner


def test_owner_command_requires_approval_then_executes(_client) -> None:  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    for capability in ["research", "analysis", "architecture", "engineering", "validation"]:
        create_agent(client, organization_id, headers, name=f"{capability.title()} Agent",
                     slug=f"owner-{capability}", capabilities=[capability])

    created = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Research a healthcare automation opportunity"},
    )
    assert created.status_code == 201
    command = created.json()
    assert command["context"]["owner_command"]["approval_status"] == "awaiting_approval"
    assert len(command["steps"]) == 5

    execute_url = (
        f"/api/v1/organizations/{organization_id}/owner-commands/{command['id']}/execute"
    )
    assert client.post(execute_url, headers=headers, json={}).status_code == 409

    approved = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["context"]["owner_command"]["approval_status"] == "approved"

    executed = client.post(execute_url, headers=headers, json={})
    assert executed.status_code == 200
    assert executed.json()["run"]["status"] == "succeeded"
    assert executed.json()["execution"]["executed_steps"] == 5

    brief = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command['id']}/brief",
        headers=headers,
    )
    assert brief.status_code == 200
    result = brief.json()
    assert result["progress"] == {"completed": 5, "total": 5}
    assert result["usage"]["execution_tokens"] > 0
    assert result["usage"]["total_tokens"] >= result["usage"]["execution_tokens"]
    assert all(step["output"] for step in result["steps"])
    assert all(step["agent_name"] for step in result["steps"])
    assert all(step["model"] == "mock-v1" for step in result["steps"])
    assert all(step["duration_ms"] is not None for step in result["steps"])

    promote_url = (
        f"/api/v1/organizations/{organization_id}/owner-commands/{command['id']}/promote"
    )
    promoted = client.post(promote_url, headers=headers)
    assert promoted.status_code == 200
    assert promoted.json()["created"] is True
    assert promoted.json()["department_name"]
    assert client.post(promote_url, headers=headers).json()["created"] is False

    promoted_brief = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command['id']}/brief",
        headers=headers,
    ).json()
    assert promoted_brief["promotion"]["project_id"] == promoted.json()["project_id"]

    goals = client.get(
        f"/api/v1/organizations/{organization_id}/goals",
        headers=headers,
    ).json()
    projects = client.get(
        f"/api/v1/organizations/{organization_id}/projects",
        headers=headers,
    ).json()
    assert len(goals) == 1
    assert len(projects) == 1
    assert projects[0]["goal_id"] == goals[0]["id"]
    assert projects[0]["metadata_json"]["owner_command_id"] == command["id"]


def test_owner_command_list_excludes_regular_orchestrations(_client) -> None:  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(f"/api/v1/organizations/{organization_id}/orchestrations",
                headers=headers, json={"objective": "Analyze a normal workflow"})
    client.post(f"/api/v1/organizations/{organization_id}/owner-commands",
                headers=headers, json={"objective": "Analyze an owner priority"})
    response = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands", headers=headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_owner_command_provisions_founding_agents_once(_client) -> None:  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/api/v1/organizations/{organization_id}/owner-commands"

    first = client.post(url, headers=headers, json={"objective": "Analyze a clinic workflow"})
    assert first.status_code == 201
    command = first.json()
    assert command["context"]["owner_command"]["approval_status"] == "awaiting_approval"
    assert command["context"]["planner"]["mode"] == "fallback"
    assert command["summary"]["unmatched_steps"] == 0
    assert all(step["assigned_agent_id"] for step in command["steps"])

    second = client.post(url, headers=headers, json={"objective": "Research another workflow"})
    assert second.status_code == 201
    agents = client.get(
        f"/api/v1/organizations/{organization_id}/agents",
        headers=headers,
    )
    assert agents.status_code == 200
    founding = [agent for agent in agents.json() if agent["slug"].startswith("seldrune-")]
    assert len(founding) == 5



def test_semantic_outcome_gate_blocks_false_success_promotion(_client) -> None:  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Produce a result that is not ready and has not been verified"},
    ).json()
    command_id = created["id"]
    client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/approve",
        headers=headers,
    )
    executed = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/execute",
        headers=headers,
        json={},
    )
    assert executed.status_code == 200
    assert executed.json()["run"]["status"] == "succeeded"

    brief = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/brief",
        headers=headers,
    ).json()
    assert brief["outcome"]["verdict"] == "not_achieved"
    assert brief["outcome"]["promotable"] is False
    assert brief["readiness"] == "blocked"

    promoted = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/promote",
        headers=headers,
    )
    assert promoted.status_code == 409
    assert "Outcome is not achieved" in promoted.json()["detail"]

    recovered = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/recover",
        headers=headers,
    )
    assert recovered.status_code == 201
    recovery = recovered.json()
    assert recovery["context"]["owner_command"]["approval_status"] == "awaiting_approval"
    assert recovery["context"]["owner_command"]["recovery_of"] == command_id
    assert recovery["context"]["recovery"]["source_command_id"] == command_id
    assert all(step["assigned_agent_id"] for step in recovery["steps"])

    repeated = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/recover",
        headers=headers,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == recovery["id"]

    source_brief = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/brief",
        headers=headers,
    ).json()
    assert source_brief["recovery_command_id"] == recovery["id"]



def test_governance_audit_log_is_scoped_filterable_and_redacted(_client) -> None:  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={
            "objective": "Audit a governed workflow",
            "context": {"api_key": "must-not-leak"},
        },
    )
    assert created.status_code == 201
    command_id = created.json()["id"]
    approved = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{command_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200

    response = client.get(
        f"/api/v1/organizations/{organization_id}/audit-log?limit=30",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_returned"] >= 2
    actions = [event["action"] for event in body["events"]]
    assert "owner_command.created" in actions
    assert "owner_command.approved" in actions
    assert all(event["resource_id"] == command_id for event in body["events"] if event["action"].startswith("owner_command."))

    filtered = client.get(
        f"/api/v1/organizations/{organization_id}/audit-log?action=owner_command.approved",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["events"]
    assert {event["action"] for event in filtered.json()["events"]} == {"owner_command.approved"}

    invalid = client.get(
        f"/api/v1/organizations/{organization_id}/audit-log?limit=0",
        headers=headers,
    )
    assert invalid.status_code == 422
