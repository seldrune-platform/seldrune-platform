from backend.app.core.orchestration import PlannedStep
from backend.app.services import tool_gateway, tool_input_defaults
from backend.app.services.live_planner import PlanResult
from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap(client, organization_id: str, headers: dict[str, str]) -> list[dict]:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap",
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    tools = client.get(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
    )
    assert tools.status_code == 200
    return tools.json()


def _tool(tools: list[dict], slug: str) -> dict:
    return next(item for item in tools if item["slug"] == slug)


def test_gmail_defaults_recipient_to_authenticated_owner(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", "gmail-test-token")
    observed = {}

    def send_message(payload, credential):
        observed.update(payload)
        assert credential == "gmail-test-token"
        return {
            "message_id": "msg-default-owner",
            "evidence": {
                "receipt_id": "gmail:msg-default-owner",
                "provider": "gmail",
            },
        }

    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("gmail", "send-message"),
        send_message,
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)
    tools = _bootstrap(client, organization_id, headers)
    gmail = _tool(tools, "gmail-send-message")

    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={
            "tool_id": gmail["id"],
            "input_data": {
                "subject": "Runtime default",
                "body": "Use the authenticated owner as recipient.",
            },
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["input_data"]["to"] == "autonomy-founder@example.com"
    assert observed["to"] == "autonomy-founder@example.com"


def test_github_merge_defaults_are_resolved_before_approval(
    client,
    monkeypatch,
) -> None:
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
    token, organization_id = register_owner(client)
    headers = _headers(token)
    tools = _bootstrap(client, organization_id, headers)
    merge_tool = _tool(tools, "github-merge-pull-request")

    requested = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={
            "tool_id": merge_tool["id"],
            "input_data": {"pull_number": 233},
        },
    )
    assert requested.status_code == 201
    run = requested.json()
    assert run["status"] == "pending_approval"
    assert run["input_data"] == {
        "pull_number": 233,
        "owner": "seldrune-platform",
        "repo": "seldrune-platform",
    }


def test_render_deploy_uses_configured_default_service_id(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SELDRUNE_RENDER_API_KEY", "render-test-token")
    monkeypatch.setattr(
        tool_input_defaults.settings,
        "render_default_service_id",
        "srv-default-123",
    )
    observed = {}

    def deploy_service(payload, credential):
        observed.update(payload)
        assert credential == "render-test-token"
        return {
            "deploy_id": "dep-default",
            "evidence": {
                "receipt_id": "render-deploy:dep-default",
                "provider": "render",
            },
        }

    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("render", "deploy-service"),
        deploy_service,
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)
    tools = _bootstrap(client, organization_id, headers)
    render = _tool(tools, "render-deploy-service")

    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={
            "tool_id": render["id"],
            "input_data": {"clear_cache": False},
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["input_data"]["service_id"] == "srv-default-123"
    assert observed["service_id"] == "srv-default-123"


def test_explicit_tool_input_overrides_runtime_defaults(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SELDRUNE_GITHUB_TOOL_TOKEN", "github-test-token")
    monkeypatch.setattr(tool_input_defaults.settings, "github_default_owner", "default-owner")
    monkeypatch.setattr(tool_input_defaults.settings, "github_default_repo", "default-repo")
    observed = {}

    def create_issue(payload, credential):
        observed.update(payload)
        return {
            "issue_id": 991,
            "evidence": {
                "receipt_id": "github-issue:991",
                "provider": "github",
            },
        }

    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("github", "create-issue"),
        create_issue,
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)
    tools = _bootstrap(client, organization_id, headers)
    issue_tool = _tool(tools, "github-create-issue")

    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={
            "tool_id": issue_tool["id"],
            "input_data": {
                "owner": "explicit-owner",
                "repo": "explicit-repo",
                "title": "Explicit target wins",
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "succeeded"
    assert observed["owner"] == "explicit-owner"
    assert observed["repo"] == "explicit-repo"


def test_tool_defaults_endpoint_reports_resolvable_fields(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", "gmail-test-token")
    monkeypatch.setenv("SELDRUNE_GITHUB_TOOL_TOKEN", "github-test-token")
    monkeypatch.setenv("SELDRUNE_RENDER_API_KEY", "render-test-token")
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
    monkeypatch.setattr(tool_input_defaults.settings, "github_default_ref", "main")
    monkeypatch.setattr(
        tool_input_defaults.settings,
        "render_default_service_id",
        "srv-default-123",
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)
    _bootstrap(client, organization_id, headers)

    response = client.get(
        f"/api/v1/organizations/{organization_id}/tool-defaults",
        headers=headers,
    )
    assert response.status_code == 200
    defaults = {item["tool_slug"]: item for item in response.json()}
    assert defaults["gmail-send-message"]["defaulted_fields"] == ["to"]
    assert defaults["github-merge-pull-request"]["defaulted_fields"] == [
        "owner",
        "repo",
    ]
    assert defaults["github-dispatch-workflow"]["defaulted_fields"] == [
        "owner",
        "ref",
        "repo",
    ]
    assert defaults["github-create-pull-request"]["defaulted_fields"] == [
        "base",
        "owner",
        "repo",
    ]
    assert defaults["render-deploy-service"]["defaulted_fields"] == ["service_id"]



def test_owner_planner_schema_omits_runtime_defaulted_required_fields(
    client,
    monkeypatch,
) -> None:
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

    def capture_plan(objective, *, adaptive_guidance, available_tools, **kwargs):
        del objective, adaptive_guidance, kwargs
        merge = next(
            item
            for item in available_tools
            if item["slug"] == "github-merge-pull-request"
        )
        observed.update(merge)
        return PlanResult(
            steps=[
                PlannedStep(
                    "Merge requested pull request",
                    "Merge PR 233 after owner confirmation.",
                    ["engineering"],
                    50,
                    False,
                    "github-merge-pull-request",
                    {"pull_number": 233},
                )
            ],
            planner_version="test-runtime-default-schema",
            metadata={"mode": "test", "tool_steps": 1},
        )

    monkeypatch.setattr(
        "backend.app.api.routes.owner_commands.build_live_plan",
        capture_plan,
    )

    token, organization_id = register_owner(client)
    headers = _headers(token)
    _bootstrap(client, organization_id, headers)

    response = client.post(
        f"/api/v1/organizations/{organization_id}/owner-commands",
        headers=headers,
        json={"objective": "Merge PR 233"},
    )
    assert response.status_code == 201
    assert observed["input_defaults"] == ["owner", "repo"]
    assert observed["input_schema"]["required"] == ["pull_number"]


def test_seldrune_repository_is_the_final_github_runtime_default(monkeypatch) -> None:
    for name in ("RENDER_GIT_REPO_SLUG", "RENDER_GIT_BRANCH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(tool_input_defaults.settings, "github_default_owner", None)
    monkeypatch.setattr(tool_input_defaults.settings, "github_default_repo", None)
    monkeypatch.setattr(tool_input_defaults.settings, "github_default_ref", None)

    targets = tool_input_defaults.production_runtime_targets()

    assert targets["github_owner"] == "seldrune-platform"
    assert targets["github_repo"] == "seldrune-platform"
    assert targets["github_full_name"] == "seldrune-platform/seldrune-platform"
    assert targets["github_ref"] == "main"
