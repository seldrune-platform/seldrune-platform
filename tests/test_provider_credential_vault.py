from backend.app.services import tool_gateway
from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_owner_can_store_and_use_encrypted_github_credential(
    client,
    monkeypatch,
) -> None:
    observed: list[str | None] = []

    def repository_info(payload, credential):
        observed.append(credential)
        return {
            "repository_id": 100,
            "full_name": f"{payload['owner']}/{payload['repo']}",
            "default_branch": "main",
            "evidence": {
                "receipt_id": "github-repository:100",
                "provider": "github",
            },
        }

    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("github", "repository-info"),
        repository_info,
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)

    saved = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/credentials",
        headers=headers,
        json={
            "provider": "github",
            "secret_value": "github-secret-one",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["provider"] == "github"
    assert body["configured"] is True
    assert body["tool_count"] == 11
    assert "github-secret-one" not in str(body)

    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    )
    assert references.status_code == 200
    github_reference = next(
        item
        for item in references.json()
        if item["slug"] == "github-tool-token"
    )
    assert github_reference["provider"] == "vault"
    assert github_reference["locator"] == "vault://stored"
    assert "github-secret-one" not in str(references.json())

    tools = client.get(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
    ).json()
    repository_tool = next(
        item
        for item in tools
        if item["slug"] == "github-repository-info"
    )
    run = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={
            "tool_id": repository_tool["id"],
            "input_data": {},
        },
    )
    assert run.status_code == 201
    assert run.json()["status"] == "succeeded"
    assert observed == ["github-secret-one"]


def test_owner_can_rotate_vault_credential_without_recreating_tools(
    client,
    monkeypatch,
) -> None:
    observed: list[str | None] = []

    def repository_info(payload, credential):
        observed.append(credential)
        return {
            "repository_id": 100,
            "evidence": {
                "receipt_id": f"github-repository:{len(observed)}",
                "provider": "github",
            },
        }

    monkeypatch.setitem(
        tool_gateway._EXTERNAL_ACTIONS,
        ("github", "repository-info"),
        repository_info,
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)
    url = f"/api/v1/organizations/{organization_id}/tool-bootstrap/credentials"

    first = client.post(
        url,
        headers=headers,
        json={"provider": "github", "secret_value": "github-secret-one"},
    )
    assert first.status_code == 200
    first_reference = first.json()["reference_id"]

    tools = client.get(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
    ).json()
    repository_tool = next(
        item
        for item in tools
        if item["slug"] == "github-repository-info"
    )

    second = client.post(
        url,
        headers=headers,
        json={"provider": "github", "secret_value": "github-secret-two"},
    )
    assert second.status_code == 200
    assert second.json()["reference_id"] == first_reference

    run = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={"tool_id": repository_tool["id"], "input_data": {}},
    )
    assert run.status_code == 201
    assert run.json()["status"] == "succeeded"
    assert observed == ["github-secret-two"]


def test_provider_credential_endpoint_rejects_unknown_provider(client) -> None:
    token, organization_id = register_owner(client)
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/credentials",
        headers=_headers(token),
        json={"provider": "unknown", "secret_value": "long-enough-secret"},
    )
    assert response.status_code == 422


def test_verified_connect_rejects_invalid_credential_without_saving(
    client,
    monkeypatch,
) -> None:
    from backend.app.api.routes import tools as tools_routes

    monkeypatch.setattr(
        tools_routes,
        "preflight_provider_credential",
        lambda provider, credential: {
            "provider": provider,
            "status": "credential_invalid",
            "verified": False,
            "detail": "Provider rejected credential.",
            "identity": {},
            "http_status": 401,
        },
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)

    response = client.post(
        (
            f"/api/v1/organizations/{organization_id}"
            "/tool-bootstrap/credentials/verified"
        ),
        headers=headers,
        json={"provider": "github", "secret_value": "definitely-bad-token"},
    )
    assert response.status_code == 422

    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    ).json()
    assert not any(item["slug"] == "github-tool-token" for item in references)


def test_verified_connect_and_disconnect_wipes_vault_credential(
    client,
    monkeypatch,
) -> None:
    from backend.app.api.routes import tools as tools_routes

    monkeypatch.setattr(
        tools_routes,
        "preflight_provider_credential",
        lambda provider, credential: {
            "provider": provider,
            "status": "verified",
            "verified": True,
            "detail": "Credential verified.",
            "identity": {"login": "owner"},
            "http_status": 200,
        },
    )
    token, organization_id = register_owner(client)
    headers = _headers(token)

    connected = client.post(
        (
            f"/api/v1/organizations/{organization_id}"
            "/tool-bootstrap/credentials/verified"
        ),
        headers=headers,
        json={"provider": "github", "secret_value": "verified-github-token"},
    )
    assert connected.status_code == 200
    assert connected.json()["verification"]["verified"] is True

    disconnected = client.delete(
        (
            f"/api/v1/organizations/{organization_id}"
            "/tool-bootstrap/credentials/github"
        ),
        headers=headers,
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["removed"] is True

    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    ).json()
    github_reference = next(
        item for item in references if item["slug"] == "github-tool-token"
    )
    assert github_reference["status"] == "disabled"

    tools = client.get(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
    ).json()
    github_tools = [item for item in tools if item["provider"] == "github"]
    assert github_tools
    assert all(item["status"] == "disabled" for item in github_tools)
    assert all(item["credential_reference_id"] is None for item in github_tools)


def test_cleanup_invalid_provider_credentials_quarantines_and_restores(
    client,
    monkeypatch,
) -> None:
    from backend.app.api.routes import tools as tools_routes

    token, organization_id = register_owner(client)
    headers = _headers(token)
    credential_url = (
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/credentials"
    )
    assert client.post(
        credential_url,
        headers=headers,
        json={"provider": "github", "secret_value": "github-bad-token"},
    ).status_code == 200
    assert client.post(
        credential_url,
        headers=headers,
        json={"provider": "render", "secret_value": "render-good-key"},
    ).status_code == 200

    monkeypatch.setattr(
        tools_routes,
        "preflight_configured_providers",
        lambda session, organization_id: [
            {
                "provider": "github",
                "status": "credential_invalid",
                "verified": False,
                "detail": "Rejected",
                "identity": {},
                "http_status": 401,
            },
            {
                "provider": "render",
                "status": "verified",
                "verified": True,
                "detail": "Verified",
                "identity": {},
                "http_status": 200,
            },
        ],
    )
    cleanup_url = (
        f"/api/v1/organizations/{organization_id}"
        "/tool-bootstrap/credentials/cleanup-invalid"
    )
    cleanup = client.post(
        cleanup_url,
        headers=headers,
        json={},
    )
    assert cleanup.status_code == 200
    body = cleanup.json()
    assert body["invalid"] == ["github"]
    assert body["removed"] == []
    assert body["quarantined"][0]["provider"] == "github"
    assert body["quarantined"][0]["secret_preserved"] is True

    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    ).json()
    status_by_slug = {item["slug"]: item["status"] for item in references}
    assert status_by_slug["github-tool-token"] == "disabled"
    assert status_by_slug["render-api-key"] == "active"

    tools = client.get(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
    ).json()
    github_tools = [item for item in tools if item["provider"] == "github"]
    assert github_tools
    assert all(item["status"] == "disabled" for item in github_tools)

    monkeypatch.setattr(
        tools_routes,
        "preflight_configured_providers",
        lambda session, organization_id: [
            {
                "provider": "github",
                "status": "verified",
                "verified": True,
                "detail": "Recovered",
                "identity": {},
                "http_status": 200,
            },
            {
                "provider": "render",
                "status": "verified",
                "verified": True,
                "detail": "Verified",
                "identity": {},
                "http_status": 200,
            },
        ],
    )
    recovered = client.post(
        cleanup_url,
        headers=headers,
        json={},
    )
    assert recovered.status_code == 200
    recovered_body = recovered.json()
    github_restore = next(
        item
        for item in recovered_body["restored"]
        if item["provider"] == "github"
    )
    assert github_restore["restored"] is True

    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    ).json()
    status_by_slug = {item["slug"]: item["status"] for item in references}
    assert status_by_slug["github-tool-token"] == "active"

    tools = client.get(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
    ).json()
    github_tools = [item for item in tools if item["provider"] == "github"]
    assert github_tools
    assert all(item["status"] == "active" for item in github_tools)
