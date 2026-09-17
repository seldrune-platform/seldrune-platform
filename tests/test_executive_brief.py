from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def _blocked_project(
    client,
    base: str,
    headers: dict[str, str],
    *,
    name: str = "Blocked Delivery",
    slug: str = "blocked-delivery",
) -> dict:
    response = client.post(
        f"{base}/projects",
        headers=headers,
        json={
            "name": name,
            "slug": slug,
            "status": "blocked",
            "priority": 95,
            "budget_limit_usd": 50,
            "resource_limit_units": 100,
        },
    )
    assert response.status_code == 201
    return response.json()


def _project_priority(
    client,
    base: str,
    headers: dict[str, str],
    project_id: str | None = None,
) -> dict:
    brief = client.get(f"{base}/executive-brief", headers=headers)
    assert brief.status_code == 200
    priorities = [item for item in brief.json()["priorities"] if item["source"] == "project"]
    if project_id is None:
        return priorities[0]
    return next(item for item in priorities if item["resource_id"] == project_id)


def test_executive_brief_reports_owner_priorities(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    initial = client.get(f"{base}/executive-brief", headers=headers)
    assert initial.status_code == 200
    body = initial.json()
    assert body["health"]["score"] == 100
    assert body["health"]["posture"] == "stable"
    assert body["governance"] == {
        "max_steps_per_command": 25,
        "max_project_budget_usd": 100.0,
        "allow_autonomous_execution": True,
    }
    assert body["operating_snapshot"]["open_goals"] == 0
    assert body["priorities"][0]["source"] == "goals"
    assert body["priorities"][0]["key"] == "no-open-goals"
    assert body["priorities"][0]["action"]["kind"] == "navigate"
    assert body["priorities"][0]["lifecycle"]["state"] == "unassigned"
    assert body["priorities"][0]["escalation"]["level"] == 0
    assert body["priorities"][0]["outcome_memory"]["confidence"] == "none"
    assert body["priorities"][0]["strategy"]["mode"] == "observe"
    assert body["priorities"][0]["strategy"]["owner_approval_required"] is False
    assert body["executive_actions"]["tracked_priorities"] == 0
    assert body["executive_actions"]["escalated_priorities"] == 0
    assert body["outcome_memory"]["learned_families"] == 0
    assert body["outcome_playbooks"] == []
    assert body["resolved_actions"] == []
    assert body["executive_strategy"] == {
        "actionable_priorities": 0,
        "history_informed_priorities": 0,
        "comparative_recommendations": 0,
        "modes": {"observe": 1},
    }

    _blocked_project(client, base, headers)
    result = client.get(f"{base}/executive-brief", headers=headers).json()
    assert result["health"]["score"] < 100
    assert result["health"]["blocked_projects"] == 1
    assert result["health"]["warning_incidents"] >= 1
    project_priority = next(
        item for item in result["priorities"] if item["source"] == "project"
    )
    assert project_priority["severity"] == "high"
    assert project_priority["key"].startswith("blocked-project:")
    assert project_priority["action"]["kind"] == "owner_command"
    assert project_priority["lifecycle"]["state"] == "unassigned"
    assert project_priority["escalation"]["level"] == 0
    assert project_priority["outcome_memory"]["family"] == "blocked-project"
    assert project_priority["strategy"]["mode"] == "baseline"
    assert project_priority["strategy"]["history_informed"] is False
    assert project_priority["strategy"]["owner_approval_required"] is True
    assert result["executive_strategy"]["actionable_priorities"] >= 1


def test_executive_priority_action_lifecycle_closes_when_evidence_clears(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    project = _blocked_project(client, base, headers)
    project_id = project["id"]
    priority = _project_priority(client, base, headers)
    endpoint = f"{base}/executive-brief/actions/{priority['key']}"

    created = client.post(endpoint, headers=headers)
    assert created.status_code == 201
    command = created.json()
    assert command["context"]["owner_command"]["approval_status"] == "awaiting_approval"
    assert command["context"]["executive_priority"]["key"] == priority["key"]
    assert command["context"]["executive_priority"]["resource_id"] == project_id
    assert command["context"]["executive_outcome_memory"]["causal_claim"] is False
    strategy = command["context"]["executive_strategy"]
    assert strategy["mode"] == "baseline"
    assert strategy["owner_approval_required"] is True
    assert strategy["causal_claim"] is False
    assert strategy["required_evidence"]
    assert "Executive strategy mode baseline" in command["objective"]

    active_brief = client.get(f"{base}/executive-brief", headers=headers).json()
    active_priority = next(
        item for item in active_brief["priorities"] if item["key"] == priority["key"]
    )
    assert active_priority["lifecycle"]["state"] == "awaiting_approval"
    assert active_priority["lifecycle"]["command_id"] == command["id"]
    assert active_priority["lifecycle"]["attempts"] == 1
    assert active_brief["executive_actions"]["tracked_priorities"] == 1

    repeated = client.post(endpoint, headers=headers)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == command["id"]

    unblocked = client.patch(
        f"{base}/projects/{project_id}",
        headers=headers,
        json={"status": "active"},
    )
    assert unblocked.status_code == 200

    resolved_brief = client.get(f"{base}/executive-brief", headers=headers).json()
    assert all(item["key"] != priority["key"] for item in resolved_brief["priorities"])
    resolved = next(
        item for item in resolved_brief["resolved_actions"] if item["key"] == priority["key"]
    )
    assert resolved["state"] == "resolved"
    assert resolved["latest_command_id"] == command["id"]
    assert resolved["latest_command_status"] == command["status"]
    assert resolved["attempts"] == 1
    assert resolved_brief["executive_actions"]["resolved_priorities"] == 1


def test_persistent_priority_escalates_after_completed_action(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    _blocked_project(client, base, headers)
    priority = _project_priority(client, base, headers)
    endpoint = f"{base}/executive-brief/actions/{priority['key']}"

    first = client.post(endpoint, headers=headers)
    assert first.status_code == 201
    first_command = first.json()

    approved = client.post(
        f"{base}/owner-commands/{first_command['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200

    executed = client.post(
        f"{base}/owner-commands/{first_command['id']}/execute",
        headers=headers,
        json={"max_steps": 50},
    )
    assert executed.status_code == 200
    assert executed.json()["run"]["status"] in {"succeeded", "partial", "failed"}

    escalated_brief = client.get(f"{base}/executive-brief", headers=headers).json()
    escalated = next(
        item for item in escalated_brief["priorities"] if item["key"] == priority["key"]
    )
    assert escalated["escalation"]["level"] == 1
    assert escalated["escalation"]["completed_attempts"] == 1
    assert escalated["escalation"]["effective_severity"] == "critical"
    assert escalated["escalation"]["alternate_strategy_required"] is True
    assert escalated["strategy"]["mode"] == "recover"
    assert escalated["strategy"]["history_informed"] is True
    assert escalated_brief["executive_actions"]["escalated_priorities"] == 1
    assert escalated_brief["executive_strategy"]["history_informed_priorities"] >= 1

    follow_up = client.post(endpoint, headers=headers)
    assert follow_up.status_code == 201
    second_command = follow_up.json()
    assert second_command["id"] != first_command["id"]
    assert second_command["objective"].startswith("Executive escalation level 1:")
    assert "Executive strategy mode recover" in second_command["objective"]
    context = second_command["context"]["executive_priority"]
    assert context["escalation_level"] == 1
    assert context["completed_attempts"] == 1
    assert context["effective_severity"] == "critical"
    strategy_context = second_command["context"]["executive_strategy"]
    assert strategy_context["mode"] == "recover"
    assert strategy_context["history_informed"] is True


def test_resolution_associated_memory_guides_similar_future_priority(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first_project = _blocked_project(
        client,
        base,
        headers,
        name="Blocked Alpha",
        slug="blocked-alpha",
    )
    first_priority = _project_priority(client, base, headers, first_project["id"])
    first_endpoint = f"{base}/executive-brief/actions/{first_priority['key']}"
    first_command = client.post(first_endpoint, headers=headers).json()

    approved = client.post(
        f"{base}/owner-commands/{first_command['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    executed = client.post(
        f"{base}/owner-commands/{first_command['id']}/execute",
        headers=headers,
        json={"max_steps": 50},
    )
    assert executed.status_code == 200
    assert executed.json()["run"]["status"] == "succeeded"

    unblocked = client.patch(
        f"{base}/projects/{first_project['id']}",
        headers=headers,
        json={"status": "active"},
    )
    assert unblocked.status_code == 200

    learned = client.get(f"{base}/executive-brief", headers=headers).json()
    assert learned["outcome_memory"]["learned_families"] == 1
    assert learned["outcome_memory"]["resolution_patterns"] == 1
    assert learned["outcome_playbooks"][0]["family"] == "blocked-project"
    assert learned["outcome_playbooks"][0]["latest"]["command_id"] == first_command["id"]

    second_project = _blocked_project(
        client,
        base,
        headers,
        name="Blocked Beta",
        slug="blocked-beta",
    )
    second_priority = _project_priority(client, base, headers, second_project["id"])
    memory = second_priority["outcome_memory"]
    assert memory["family"] == "blocked-project"
    assert memory["confidence"] == "medium"
    assert memory["resolution_patterns"] == 1
    assert memory["preferred_pattern"]["command_id"] == first_command["id"]
    assert memory["causal_claim"] is False
    strategy = second_priority["strategy"]
    assert strategy["mode"] == "reuse"
    assert strategy["history_informed"] is True
    assert strategy["preferred_reference_command_id"] == first_command["id"]

    second_endpoint = f"{base}/executive-brief/actions/{second_priority['key']}"
    second_command = client.post(second_endpoint, headers=headers)
    assert second_command.status_code == 201
    body = second_command.json()
    context = body["context"]["executive_outcome_memory"]
    assert context["preferred_reference_command_id"] == first_command["id"]
    assert context["resolution_patterns"] == 1
    assert context["causal_claim"] is False
    strategy_context = body["context"]["executive_strategy"]
    assert strategy_context["mode"] == "reuse"
    assert strategy_context["preferred_reference_command_id"] == first_command["id"]
    assert strategy_context["owner_approval_required"] is True
    assert "Executive strategy mode reuse" in body["objective"]
    assert "resolution-associated pattern" in body["objective"]
    assert "supporting evidence rather than proof of causation" in body["objective"]


def test_executive_priority_action_rejects_navigation_and_stale_keys(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    navigation = client.post(
        f"{base}/executive-brief/actions/no-open-goals",
        headers=headers,
    )
    assert navigation.status_code == 409

    stale = client.post(
        f"{base}/executive-brief/actions/not-a-current-priority",
        headers=headers,
    )
    assert stale.status_code == 409


def test_executive_brief_assets_are_served(client) -> None:
    page = client.get("/console-assets/executive-brief.html")
    assert page.status_code == 200
    assert "Executive Brief" in page.text
    assert "EXECUTIVE OUTCOME MEMORY" in page.text
    assert "outcome-playbooks" in page.text
    assert "/console-assets/executive-brief.js" in page.text

    script = client.get("/console-assets/executive-brief.js")
    assert script.status_code == 200
    assert "/executive-brief/actions/" in script.text
    assert "resolution-associated pattern" in script.text
    assert "Learned families" in script.text
    assert "Strategy-informed" in script.text
    assert "Strategy recommendations" in script.text
    assert "strategyLabel" in script.text

    board = client.get("/console-assets/organization-board.html")
    assert board.status_code == 200
    assert "/console-assets/executive-brief.html" in board.text
