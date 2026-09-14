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
