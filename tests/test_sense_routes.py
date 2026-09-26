from backend.app.core.orchestration import PlannedStep
from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def test_sense_endpoint_reports_go_for_live_well_matched_plan(client, monkeypatch) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    class LivePlan:
        planner_version = "live-model-v2"
        metadata = {"mode": "live", "provider": "openai", "model": "test-live-model"}
        steps = [PlannedStep("Analyze", "Analyze objective", ["analysis"], 80)]

    monkeypatch.setattr(
        "backend.app.api.routes.owner_commands.build_live_plan",
        lambda objective, **kwargs: LivePlan,
    )
    created = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Analyze this opportunity"},
    )
    assert created.status_code == 201
    run_id = created.json()["id"]

    sense = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands/{run_id}/sense",
        headers=headers,
    )
    assert sense.status_code == 200
    assert sense.json()["decision"] == "GO"
    assert sense.json()["score"] >= 65


def test_sense_review_requires_owner_override(client, monkeypatch) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    class WeakFitPlan:
        planner_version = "live-model-v2"
        metadata = {"mode": "live", "provider": "openai", "model": "test-live-model"}
        steps = [
            PlannedStep(
                "Cross-domain analysis",
                "Analyze using research and analysis capabilities",
                ["analysis", "research"],
                80,
            )
        ]

    monkeypatch.setattr(
        "backend.app.api.routes.owner_commands.build_live_plan",
        lambda objective, **kwargs: WeakFitPlan,
    )
    created = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Analyze a cross-domain opportunity"},
    )
    assert created.status_code == 201
    run_id = created.json()["id"]

    approved = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{run_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200

    blocked = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{run_id}/execute",
        headers=headers,
        json={},
    )
    assert blocked.status_code == 409
    assert "Sense Layer REVIEW" in blocked.json()["detail"]

    override = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{run_id}/sense/override",
        headers=headers,
    )
    assert override.status_code == 200
    assert override.json()["status"] == "approved"

    executed = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{run_id}/execute",
        headers=headers,
        json={},
    )
    assert executed.status_code == 200


def test_sense_uses_successful_similar_outcome_and_reflection_memory(client, monkeypatch) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    class LivePlan:
        planner_version = "live-model-v2"
        metadata = {"mode": "live", "provider": "openai", "model": "test-live-model"}
        steps = [
            PlannedStep(
                "Analyze payment automation",
                "Analyze a payment automation workflow",
                ["analysis"],
                80,
            )
        ]

    monkeypatch.setattr(
        "backend.app.api.routes.owner_commands.build_live_plan",
        lambda objective, **kwargs: LivePlan,
    )

    first = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Analyze payment automation workflow"},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    assert client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{first_id}/approve",
        headers=headers,
    ).status_code == 200
    executed = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands/{first_id}/execute",
        headers=headers,
        json={},
    )
    assert executed.status_code == 200
    reflection = executed.json()["run"]["summary"]["reflection"]
    assert reflection["version"] == "reflection-v1"
    assert "orchestration_completed_successfully" in reflection["strengths"]
    assert reflection["capability_performance"]["analysis"]["succeeded"] == 1
    assert reflection["recommendations"]

    second = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Analyze payment automation workflow improvements"},
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    sense = client.get(
        f"/api/v1/organizations/{organization_id}/owner-commands/{second_id}/sense",
        headers=headers,
    )
    assert sense.status_code == 200
    signals = sense.json()["signals"]
    memory = signals["outcome_memory"]
    assert memory["sample_count"] >= 1
    assert memory["success_rate"] == 1.0
    assert memory["score_adjustment"] > 0
    assert memory["reason"] == "similar_history_positive"

    reflection_memory = signals["reflection_memory"]
    assert reflection_memory["sample_count"] >= 1
    assert reflection_memory["capability_success_rate"] == 1.0
    assert reflection_memory["score_adjustment"] > 0
    assert reflection_memory["reason"] == "reflection_lessons_positive"
    assert reflection_memory["lessons"]
    assert signals["learning_adjustment"] > 0


def test_system_sense_reports_owner_scoped_runtime_signals(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        f"/api/v1/organizations/{organization_id}/sense/system",
        headers=headers,
    )

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["organization_id"] == str(organization_id)
    assert snapshot["owner"]["id"]
    assert "task_status" in snapshot["system"]["monitored_signals"]
    assert snapshot["agents"]["total"] >= 0
    assert snapshot["tasks"]["open"] >= 0
    assert snapshot["security_events"]["open"] >= 0
    assert {item["provider"] for item in snapshot["model_providers"]} >= {
        "auto",
        "gemini",
        "anthropic",
    }
    assert all("api_key" not in item for item in snapshot["model_providers"])


def test_owner_continuity_can_be_saved_loaded_and_cleared(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = f"/api/v1/organizations/{organization_id}/sense/owner-continuity"

    saved = client.put(
        endpoint,
        headers=headers,
        json={"content": "Keep plans concise and show test results."},
    )
    assert saved.status_code == 200
    assert saved.json()["saved"] is True

    loaded = client.get(endpoint, headers=headers)
    assert loaded.status_code == 200
    assert loaded.json()["content"] == "Keep plans concise and show test results."

    cleared = client.put(endpoint, headers=headers, json={"content": ""})
    assert cleared.status_code == 200
    assert cleared.json()["saved"] is False
    assert client.get(endpoint, headers=headers).json()["content"] == ""
