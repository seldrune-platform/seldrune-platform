from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


_BOOTSTRAP_ENV_VARS = (
    "SELDRUNE_GMAIL_TOOL_CREDENTIAL",
    "SELDRUNE_GITHUB_TOOL_TOKEN",
    "SELDRUNE_RENDER_API_KEY",
)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _clear_bootstrap_env(monkeypatch) -> None:
    for name in _BOOTSTRAP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_tool_bootstrap_status_reports_missing_provider_secrets(
    client,
    monkeypatch,
) -> None:
    _clear_bootstrap_env(monkeypatch)
    token, organization_id = register_owner(client)
    response = client.get(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/status",
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ready_actions"] == 0
    assert body["fully_ready"] is False
    providers = {item["provider"]: item for item in body["providers"]}
    assert set(providers) == {"gmail", "github", "render"}
    assert providers["gmail"]["credential_env_locator"] == (
        "SELDRUNE_GMAIL_TOOL_CREDENTIAL"
    )
    assert providers["github"]["credential_env_locator"] == (
        "SELDRUNE_GITHUB_TOOL_TOKEN"
    )
    assert providers["render"]["credential_env_locator"] == "SELDRUNE_RENDER_API_KEY"
    assert all(item["secret_available"] is False for item in providers.values())


def test_tool_bootstrap_activates_configured_provider_idempotently(
    client,
    monkeypatch,
) -> None:
    _clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("SELDRUNE_GITHUB_TOOL_TOKEN", "github-test-token")
    token, organization_id = register_owner(client)
    headers = _headers(token)
    url = f"/api/v1/organizations/{organization_id}/tool-bootstrap"

    first = client.post(url, headers=headers, json={})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["created_references"] == ["github-tool-token"]
    assert set(first_body["created_tools"]) == {
        "github-create-issue",
        "github-comment",
        "github-create-pull-request",
        "github-merge-pull-request",
        "github-dispatch-workflow",
    }
    assert "SELDRUNE_GMAIL_TOOL_CREDENTIAL" in first_body["missing_env_locators"]
    assert "SELDRUNE_RENDER_API_KEY" in first_body["missing_env_locators"]
    assert "github-test-token" not in str(first_body)

    second = client.post(url, headers=headers, json={})
    assert second.status_code == 200
    assert second.json()["created_references"] == []
    assert second.json()["created_tools"] == []

    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    )
    assert references.status_code == 200
    github_references = [
        item for item in references.json() if item["slug"] == "github-tool-token"
    ]
    assert len(github_references) == 1
    assert github_references[0]["locator"] == "SELDRUNE_GITHUB_TOOL_TOKEN"

    tools = client.get(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
    )
    assert tools.status_code == 200
    github_tools = [item for item in tools.json() if item["provider"] == "github"]
    assert len(github_tools) == 5
    dispatch = next(
        item for item in github_tools if item["action_name"] == "dispatch-workflow"
    )
    assert dispatch["risk_level"] == "high"
    assert dispatch["approval_mode"] == "always"

    status = client.get(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/status",
        headers=headers,
    ).json()
    github = next(item for item in status["providers"] if item["provider"] == "github")
    assert github["ready"] is True
    assert all(action["ready"] for action in github["actions"])


def test_owner_command_auto_activates_configured_provider_tools(
    client,
    monkeypatch,
) -> None:
    _clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("SELDRUNE_RENDER_API_KEY", "render-test-token")
    token, organization_id = register_owner(client)
    headers = _headers(token)
    command_url = f"/api/v1/organizations/{organization_id}/owner-commands"

    first = client.post(
        command_url,
        headers=headers,
        json={"objective": "Analyze production deployment readiness"},
    )
    assert first.status_code == 201

    tools_url = f"/api/v1/organizations/{organization_id}/tools"
    tools = client.get(tools_url, headers=headers)
    assert tools.status_code == 200
    render_tools = [item for item in tools.json() if item["provider"] == "render"]
    assert len(render_tools) == 1
    assert render_tools[0]["slug"] == "render-deploy-service"

    second = client.post(
        command_url,
        headers=headers,
        json={"objective": "Review deployment evidence again"},
    )
    assert second.status_code == 201
    tools = client.get(tools_url, headers=headers).json()
    assert len([item for item in tools if item["provider"] == "render"]) == 1
