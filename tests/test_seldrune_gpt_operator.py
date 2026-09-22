from tests.test_autonomous_execution import client as _client  # noqa: F401
from backend.app.core.orchestration import PlannedStep
from backend.app.services import tool_gateway, tool_input_defaults
from backend.app.services.live_planner import PlanResult
from tests.test_autonomous_execution import register_owner


def test_operator_risk_classification_is_explicit():
    from backend.app.api.routes.seldrune_gpt import _operator_risk_reasons

    assert _operator_risk_reasons("Analyze the organization") == []
    assert _operator_risk_reasons("Deploy to production and send an email") == []
    reasons = _operator_risk_reasons(
        "Delete records, pay invoice, rotate API key, sign contract, merge PR 233"
    )
    assert "destructive_change" in reasons
    assert "financial_commitment" in reasons
    assert "credential_or_access_change" in reasons
    assert "legal_or_people_commitment" in reasons
    assert "repository_merge" in reasons





def test_external_action_intents_map_to_registered_provider_actions():
    from backend.app.api.routes.seldrune_gpt import _required_external_tool_actions

    assert _required_external_tool_actions("Send an email to the owner") == [
        ("gmail", "send-message")
    ]
    assert _required_external_tool_actions("Merge PR 233") == [
        ("github", "merge-pull-request")
    ]
    assert _required_external_tool_actions("Create a pull request for this branch") == [
        ("github", "create-pull-request")
    ]
    assert _required_external_tool_actions("Trigger the GitHub Actions workflow") == [
        ("github", "dispatch-workflow")
    ]
    assert _required_external_tool_actions("Deploy this release to production") == [
        ("render", "deploy-service")
    ]


def test_gpt_operator_requires_auth(client):
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        json={"order": "Analyze the organization status"},
    )
    assert response.status_code in {401, 403}


def test_gpt_capabilities_report_registered_tools_and_provider_readiness(
    _client,  # noqa: F811
    monkeypatch,
):
    client = _client
    monkeypatch.setenv("SELDRUNE_GITHUB_TOOL_TOKEN", "github-test-token")
    monkeypatch.delenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", raising=False)
    monkeypatch.delenv("SELDRUNE_RENDER_API_KEY", raising=False)
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    bootstrap = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap",
        headers=headers,
        json={},
    )
    assert bootstrap.status_code == 200

    response = client.get(
        f"/api/v1/organizations/{organization_id}/gpt/capabilities",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider_readiness"]["github"] is True
    assert body["provider_readiness"]["gmail"] is False
    assert body["provider_readiness"]["render"] is False
    assert "github-merge-pull-request" in body["registered_tools"]
    assert "SELDRUNE_GITHUB_TOOL_TOKEN" not in body["configuration_hints"]
    assert "SELDRUNE_GMAIL_TOOL_CREDENTIAL" in body["configuration_hints"]
    assert "SELDRUNE_RENDER_API_KEY" in body["configuration_hints"]


def test_safe_owner_order_executes_in_one_request(_client):  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        headers=headers,
        json={"order": "Analyze the organization and produce a verified operating brief"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_required"] is False
    assert body["status"] in {"completed", "partial"}
    assert body["command_id"]
    assert body["executed_steps"] > 0
    assert body["evidence_url"].endswith(f"/{body['command_id']}/brief")


def test_external_order_requires_ready_provider_tools(
    _client,  # noqa: F811
    monkeypatch,
):
    client = _client
    for name in (
        "SELDRUNE_GMAIL_TOOL_CREDENTIAL",
        "SELDRUNE_RENDER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        headers=headers,
        json={"order": "Deploy this release to production and notify the owner by email"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "configuration_required"
    assert body["approval_required"] is False
    assert body["command_id"] is None
    assert set(body["missing_tools"]) == {
        "gmail:send-message",
        "render:deploy-service",
    }
    assert set(body["configuration_hints"]) == {
        "SELDRUNE_GMAIL_TOOL_CREDENTIAL",
        "SELDRUNE_RENDER_API_KEY",
    }
    assert body["halted_reason"] == "required_external_tool_unavailable"


def test_operator_compiles_missing_ready_email_tool_deterministically(
    _client,  # noqa: F811
    monkeypatch,
):
    client = _client
    monkeypatch.setenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", "gmail-test-token")
    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("gmail", "send-message"),
        lambda payload, credential: {
            "message_id": "msg-compiled-1",
            "to": payload["to"],
            "evidence": {
                "receipt_id": "gmail:msg-compiled-1",
                "provider": "gmail",
            },
        },
    )
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        headers=headers,
        json={"order": "Send an email to the owner with release status"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["command_id"]
    assert body["executed_steps"] == 1
    assert body["failed_steps"] == 0
    assert body["blocked_steps"] == 0

    brief = client.get(body["evidence_url"], headers=headers)
    assert brief.status_code == 200
    command = brief.json()
    assert command["progress"] == {"completed": 1, "total": 1}
    assert command["steps"][0]["output"]["execution_type"] == "tool"
    assert (
        command["steps"][0]["output"]["evidence"]["receipt_id"]
        == "gmail:msg-compiled-1"
    )


def test_operator_executes_required_planned_tool_with_receipt(
    _client,  # noqa: F811
    monkeypatch,
):
    client = _client
    monkeypatch.setenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", "gmail-test-token")

    def planned_email(*args, **kwargs):
        del args, kwargs
        return PlanResult(
            steps=[
                PlannedStep(
                    "Notify owner",
                    "Send the verified release status to the owner.",
                    ["analysis"],
                    50,
                    False,
                    "gmail-send-message",
                    {
                        "to": "owner@example.com",
                        "subject": "Release status",
                        "body": "Verified release status.",
                    },
                )
            ],
            planner_version="test-tool-plan",
            metadata={"mode": "test", "tool_steps": 1},
        )

    monkeypatch.setattr(
        "backend.app.api.routes.owner_commands.build_live_plan",
        planned_email,
    )
    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("gmail", "send-message"),
        lambda payload, credential: {
            "message_id": "msg-test-1",
            "evidence": {
                "receipt_id": "gmail:msg-test-1",
                "provider": "gmail",
            },
        },
    )

    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        headers=headers,
        json={"order": "Send an email to owner@example.com with release status"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["executed_steps"] == 1
    assert body["failed_steps"] == 0
    assert body["blocked_steps"] == 0
    assert body["command_id"]
    assert body["evidence_url"].endswith(f"/{body['command_id']}/brief")


def test_merge_pr_order_is_one_tool_step_then_executes_after_confirmation(
    _client,  # noqa: F811
    monkeypatch,
):
    client = _client
    monkeypatch.setenv("SELDRUNE_GITHUB_TOOL_TOKEN", "github-test-token")
    monkeypatch.setattr(
        tool_input_defaults.settings,
        "github_default_owner",
        "seldrune-platform",
    )
    monkeypatch.setattr(
        tool_input_defaults.settings,
        "github_default_repo",
        "seldrune-platform",
    )
    observed = {}

    def merge_pull_request(payload, credential):
        observed.update(payload)
        assert credential == "github-test-token"
        return {
            "pull_number": payload["pull_number"],
            "merged": True,
            "sha": "merge-sha-233",
            "evidence": {
                "receipt_id": "github-merge:merge-sha-233",
                "provider": "github",
            },
        }

    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("github", "merge-pull-request"),
        merge_pull_request,
    )
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    operate_url = f"/api/v1/organizations/{organization_id}/gpt/operate"

    first = client.post(
        operate_url,
        headers=headers,
        json={"order": "Merge PR 233"},
    )
    assert first.status_code == 200
    pending = first.json()
    assert pending["status"] == "approval_required"
    assert pending["approval_required"] is True
    assert pending["executed_steps"] == 0
    assert "repository_merge" in pending["risk_reasons"]

    command = client.get(
        pending["evidence_url"],
        headers=headers,
    )
    assert command.status_code == 200
    assert command.json()["progress"] == {"completed": 0, "total": 1}

    confirmed = client.post(
        operate_url,
        headers=headers,
        json={
            "order": "Merge PR 233",
            "command_id": pending["command_id"],
            "confirm_sensitive_action": True,
        },
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "completed"
    assert body["executed_steps"] == 1
    assert observed == {
        "pull_number": 233,
        "owner": "seldrune-platform",
        "repo": "seldrune-platform",
    }

    brief = client.get(body["evidence_url"], headers=headers).json()
    assert brief["progress"] == {"completed": 1, "total": 1}
    assert (
        brief["steps"][0]["output"]["evidence"]["receipt_id"]
        == "github-merge:merge-sha-233"
    )


def test_high_impact_owner_order_pauses_for_fresh_confirmation(_client):  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        headers=headers,
        json={"order": "Delete the records and pay the invoice"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approval_required"
    assert body["approval_required"] is True
    assert "destructive_change" in body["risk_reasons"]
    assert "financial_commitment" in body["risk_reasons"]
    assert body["executed_steps"] == 0
