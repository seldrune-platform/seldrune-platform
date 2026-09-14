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
