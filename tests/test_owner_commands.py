from tests.test_autonomous_execution import client, create_agent, register_owner


def test_owner_command_requires_approval_then_executes(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    for capability in ["research", "analysis", "architecture"]:
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
    assert len(command["steps"]) == 3

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
    assert executed.json()["execution"]["executed_steps"] == 3


def test_owner_command_list_excludes_regular_orchestrations(client) -> None:
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
