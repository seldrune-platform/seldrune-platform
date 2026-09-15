from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def test_organization_kernel_bootstrap_and_operating_cycle(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first_bootstrap = client.post(f"{base}/organization-kernel/bootstrap", headers=headers)
    assert first_bootstrap.status_code == 200
    assert first_bootstrap.json()["created_departments"] == 5
    assert first_bootstrap.json()["snapshot"]["counts"]["departments"] == 5

    second_bootstrap = client.post(f"{base}/organization-kernel/bootstrap", headers=headers)
    assert second_bootstrap.status_code == 200
    assert second_bootstrap.json()["created_departments"] == 0

    departments = client.get(f"{base}/departments", headers=headers)
    assert departments.status_code == 200
    by_slug = {department["slug"]: department for department in departments.json()}
    research = by_slug["research-intelligence"]
    engineering = by_slug["engineering-automation"]

    goal = client.post(
        f"{base}/goals",
        headers=headers,
        json={
            "title": "Launch a repeatable healthcare automation offer",
            "description": "Validate demand and convert the strongest workflow into delivery.",
            "department_id": research["id"],
            "status": "active",
            "priority": 92,
            "target_metric": "qualified_pilots",
            "target_value": 3,
        },
    )
    assert goal.status_code == 201
    goal_body = goal.json()

    project = client.post(
        f"{base}/projects",
        headers=headers,
        json={
            "name": "Healthcare Automation Pilot",
            "slug": "healthcare-automation-pilot",
            "description": "Research, build, validate, and package one automation pilot.",
            "department_id": engineering["id"],
            "goal_id": goal_body["id"],
            "status": "planned",
            "priority": 95,
            "budget_limit_usd": 1000,
            "resource_limit_units": 100,
        },
    )
    assert project.status_code == 201
    project_body = project.json()

    launched = client.post(
        f"{base}/projects/{project_body['id']}/launch",
        headers=headers,
    )
    assert launched.status_code == 201
    delivery_command = launched.json()
    assert delivery_command["context"]["owner_command"]["approval_status"] == (
        "awaiting_approval"
    )
    assert delivery_command["context"]["project_delivery"]["project_id"] == project_body["id"]
    assert all(step["assigned_agent_id"] for step in delivery_command["steps"])

    repeated_launch = client.post(
        f"{base}/projects/{project_body['id']}/launch",
        headers=headers,
    )
    assert repeated_launch.status_code == 201
    assert repeated_launch.json()["id"] == delivery_command["id"]

    launched_project = client.get(f"{base}/projects", headers=headers).json()[0]
    assert launched_project["status"] == "active"
    assert launched_project["metadata_json"]["delivery_command_id"] == delivery_command["id"]

    delegation = client.post(
        f"{base}/delegations",
        headers=headers,
        json={
            "source_department_id": research["id"],
            "target_department_id": engineering["id"],
            "project_id": project_body["id"],
            "goal_id": goal_body["id"],
            "title": "Convert validated research into pilot architecture",
            "priority": 90,
            "requested_resource_units": 25,
        },
    )
    assert delegation.status_code == 201
    assert delegation.json()["status"] == "proposed"

    updated_project = client.patch(
        f"{base}/projects/{project_body['id']}",
        headers=headers,
        json={"budget_spent_usd": 250, "resource_used_units": 20},
    )
    assert updated_project.status_code == 200
    assert updated_project.json()["budget_spent_usd"] == 250

    updated_delegation = client.patch(
        f"{base}/delegations/{delegation.json()['id']}",
        headers=headers,
        json={"status": "accepted"},
    )
    assert updated_delegation.status_code == 200

    snapshot = client.get(f"{base}/organization-kernel", headers=headers)
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["counts"]["departments"] == 5
    assert body["counts"]["open_goals"] == 1
    assert body["counts"]["active_projects"] == 1
    assert body["counts"]["open_delegations"] == 1
    assert body["resources"]["active_project_budget_limit_usd"] == 1000
    assert body["resources"]["active_project_budget_spent_usd"] == 250
    assert body["resources"]["budget_utilization"] == 0.25
    assert body["resources"]["resource_utilization"] == 0.2
    assert body["priorities"]["top_projects"][0]["name"] == "Healthcare Automation Pilot"


def test_organization_kernel_rejects_same_department_delegation(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    assert client.post(f"{base}/organization-kernel/bootstrap", headers=headers).status_code == 200
    department = client.get(f"{base}/departments", headers=headers).json()[0]

    response = client.post(
        f"{base}/delegations",
        headers=headers,
        json={
            "source_department_id": department["id"],
            "target_department_id": department["id"],
            "title": "Invalid self delegation",
        },
    )
    assert response.status_code == 422



def test_delivery_outcome_completes_project_and_goal(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    client.post(f"{base}/organization-kernel/bootstrap", headers=headers)
    department = client.get(f"{base}/departments", headers=headers).json()[0]
    goal = client.post(
        f"{base}/goals",
        headers=headers,
        json={
            "title": "Verify a governed delivery lifecycle",
            "department_id": department["id"],
            "status": "planned",
            "target_metric": "verified_deliveries",
            "target_value": 1,
        },
    ).json()
    project = client.post(
        f"{base}/projects",
        headers=headers,
        json={
            "name": "Lifecycle verification",
            "slug": "lifecycle-verification",
            "department_id": department["id"],
            "goal_id": goal["id"],
            "status": "planned",
            "budget_limit_usd": 10,
            "resource_limit_units": 20,
        },
    ).json()
    command = client.post(
        f"{base}/projects/{project['id']}/launch",
        headers=headers,
    ).json()
    command_id = command["id"]
    assert command["context"]["project_delivery"]["project_id"] == project["id"]
    approved = client.post(
        f"{base}/owner-commands/{command_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["context"]["project_delivery"]["project_id"] == project["id"]
    executed = client.post(
        f"{base}/owner-commands/{command_id}/execute",
        headers=headers,
        json={},
    )
    assert executed.status_code == 200
    assert executed.json()["run"]["status"] == "succeeded"
    governor = executed.json()["run"]["summary"]["portfolio_governor"]
    assert governor["allowed"] is True
    assert governor["remaining_resource_units"] == 20
    assert executed.json()["run"]["summary"]["project_delivery_sync"]["verdict"] == "achieved"

    completed = client.get(f"{base}/projects", headers=headers).json()[0]
    assert completed["status"] == "completed"
    assert completed["metadata_json"]["delivery_state"] == "verified_complete"
    assert completed["metadata_json"]["delivery_outcome"]["verdict"] == "achieved"
    assert completed["resource_used_units"] > 0

    achieved_goal = client.get(f"{base}/goals", headers=headers).json()[0]
    assert achieved_goal["status"] == "achieved"
    assert achieved_goal["current_value"] == 1

    snapshot = client.get(f"{base}/organization-kernel", headers=headers).json()
    assert snapshot["counts"]["active_projects"] == 0
    assert snapshot["counts"]["blocked_projects"] == 0



def test_blocked_project_creates_idempotent_governed_recovery(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    client.post(f"{base}/organization-kernel/bootstrap", headers=headers)
    department = client.get(f"{base}/departments", headers=headers).json()[0]
    project = client.post(
        f"{base}/projects",
        headers=headers,
        json={
            "name": "Recovery verification",
            "slug": "recovery-verification",
            "description": "Produce a result that is not ready and has not been verified.",
            "department_id": department["id"],
            "status": "planned",
            "budget_limit_usd": 10,
            "resource_limit_units": 20,
        },
    ).json()
    command = client.post(
        f"{base}/projects/{project['id']}/launch",
        headers=headers,
    ).json()
    client.post(
        f"{base}/owner-commands/{command['id']}/approve",
        headers=headers,
    )
    executed = client.post(
        f"{base}/owner-commands/{command['id']}/execute",
        headers=headers,
        json={},
    )
    assert executed.status_code == 200
    assert executed.json()["run"]["summary"]["project_delivery_sync"]["verdict"] == (
        "not_achieved"
    )

    blocked = client.get(f"{base}/projects", headers=headers).json()[0]
    assert blocked["status"] == "blocked"

    recovered = client.post(
        f"{base}/projects/{project['id']}/recover",
        headers=headers,
    )
    assert recovered.status_code == 201
    recovery = recovered.json()
    assert recovery["context"]["owner_command"]["approval_status"] == "awaiting_approval"
    assert recovery["context"]["owner_command"]["recovery_of"] == command["id"]
    assert recovery["context"]["project_delivery"]["project_id"] == project["id"]
    assert recovery["context"]["project_delivery"]["recovery_of_command_id"] == command["id"]

    repeated = client.post(
        f"{base}/projects/{project['id']}/recover",
        headers=headers,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == recovery["id"]

    updated = client.get(f"{base}/projects", headers=headers).json()[0]
    assert updated["metadata_json"]["recovery_command_id"] == recovery["id"]
    assert updated["metadata_json"]["delivery_state"] == (
        "recovery_awaiting_owner_approval"
    )



def test_portfolio_governor_blocks_exhausted_project_resources(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    client.post(f"{base}/organization-kernel/bootstrap", headers=headers)
    department = client.get(f"{base}/departments", headers=headers).json()[0]

    cases = (
        {
            "name": "No delivery capacity",
            "slug": "no-delivery-capacity",
            "budget_limit_usd": 10,
            "budget_spent_usd": 0,
            "resource_limit_units": 0,
            "expected": "capacity units",
        },
        {
            "name": "Exhausted delivery budget",
            "slug": "exhausted-delivery-budget",
            "budget_limit_usd": 10,
            "budget_spent_usd": 10,
            "resource_limit_units": 20,
            "expected": "budget is exhausted",
        },
    )
    for case in cases:
        project = client.post(
            f"{base}/projects",
            headers=headers,
            json={
                "name": case["name"],
                "slug": case["slug"],
                "department_id": department["id"],
                "status": "planned",
                "budget_limit_usd": case["budget_limit_usd"],
                "budget_spent_usd": case["budget_spent_usd"],
                "resource_limit_units": case["resource_limit_units"],
            },
        ).json()
        command = client.post(
            f"{base}/projects/{project['id']}/launch",
            headers=headers,
        )
        assert command.status_code == 201
        command_id = command.json()["id"]
        client.post(
            f"{base}/owner-commands/{command_id}/approve",
            headers=headers,
        )
        blocked = client.post(
            f"{base}/owner-commands/{command_id}/execute",
            headers=headers,
            json={},
        )
        assert blocked.status_code == 409
        assert case["expected"] in blocked.json()["detail"]

    projects = client.get(f"{base}/projects", headers=headers).json()
    assert all(project["status"] == "active" for project in projects)
    assert all(project["resource_used_units"] == 0 for project in projects)
