import httpx

from backend.app.services import provider_preflight
from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _response(
    status_code: int,
    *,
    json_data: dict | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://provider.example.test/preflight")
    if json_data is None:
        return httpx.Response(status_code, request=request)
    return httpx.Response(status_code, json=json_data, request=request)


def test_provider_preflight_is_non_destructive_and_redacts_credentials(
    client,
    monkeypatch,
) -> None:
    monkeypatch.delenv("SELDRUNE_CI_RECEIPT_HMAC_KEY", raising=False)
    monkeypatch.setenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", "gmail-secret-token")
    monkeypatch.setenv("SELDRUNE_GITHUB_TOOL_TOKEN", "github-secret-token")
    monkeypatch.setenv("SELDRUNE_RENDER_API_KEY", "render-secret-token")

    observed: list[tuple[str, str]] = []

    def fake_get(url, *, headers, timeout):
        observed.append((url, headers.get("Authorization", "")))
        if "gmail.googleapis.com" in url:
            return _response(
                403,
                json_data={"error": {"message": "Insufficient Permission"}},
            )
        if "api.github.com/user" in url:
            return _response(
                200,
                json_data={"login": "seldrune-owner", "id": 99},
            )
        if "api.github.com/repos/seldrune-platform/seldrune-platform" in url:
            return _response(
                200,
                json_data={
                    "id": 700,
                    "full_name": "seldrune-platform/seldrune-platform",
                    "default_branch": "main",
                },
            )
        if "api.render.com/v1/users" in url:
            return _response(
                200,
                json_data={
                    "id": "usr-c123",
                    "email": "owner@example.com",
                    "name": "Seldrune Owner",
                },
            )
        raise AssertionError(f"Unexpected preflight URL: {url}")

    monkeypatch.setattr(provider_preflight.httpx, "get", fake_get)

    token, organization_id = register_owner(client)
    headers = _headers(token)
    bootstrap = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap",
        headers=headers,
        json={},
    )
    assert bootstrap.status_code == 200

    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/preflight",
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] == 2
    assert body["total"] == 4

    providers = {item["provider"]: item for item in body["providers"]}
    assert providers["gmail"]["status"] == "scope_limited"
    assert providers["gmail"]["verified"] is False
    assert providers["github"]["status"] == "verified"
    assert providers["github"]["identity"]["login"] == "seldrune-owner"
    assert providers["github"]["identity"]["repository"] == (
        "seldrune-platform/seldrune-platform"
    )
    assert providers["render"]["status"] == "verified"
    assert providers["render"]["identity"]["id"] == "usr-c123"
    assert providers["portable-ci"]["status"] == "not_configured"

    assert {
        url
        for url, _authorization in observed
    } == {
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        "https://api.github.com/user",
        "https://api.github.com/repos/seldrune-platform/seldrune-platform",
        "https://api.render.com/v1/users",
    }
    output = str(body)
    assert "gmail-secret-token" not in output
    assert "github-secret-token" not in output
    assert "render-secret-token" not in output



def test_github_app_preflight_uses_installation_repository_access(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        provider_preflight,
        "production_runtime_targets",
        lambda: {
            "github_full_name": "seldrune-platform/seldrune-platform",
        },
    )
    monkeypatch.setattr(
        provider_preflight,
        "_github_app_config",
        lambda credential: ("12345", "777", credential),
    )
    monkeypatch.setattr(
        provider_preflight,
        "_github_headers",
        lambda credential: {
            "Authorization": "Bearer installation-token",
            "Accept": "application/vnd.github+json",
        },
    )

    observed: list[str] = []

    def fake_get(url, *, headers, timeout):
        observed.append(url)
        assert headers["Authorization"] == "Bearer installation-token"
        assert url == (
            "https://api.github.com/repos/"
            "seldrune-platform/seldrune-platform"
        )
        return _response(
            200,
            json_data={
                "id": 700,
                "full_name": "seldrune-platform/seldrune-platform",
                "default_branch": "main",
            },
        )

    monkeypatch.setattr(provider_preflight.httpx, "get", fake_get)

    result = provider_preflight.preflight_provider_credential(
        "github",
        "-----BEGIN PRIVATE KEY-----\nredacted\n-----END PRIVATE KEY-----",
    )

    assert result["verified"] is True
    assert result["status"] == "verified"
    assert result["identity"]["auth_type"] == "github_app"
    assert result["identity"]["app_id"] == "12345"
    assert result["identity"]["installation_id"] == "777"
    assert result["identity"]["repository"] == (
        "seldrune-platform/seldrune-platform"
    )
    assert observed == [
        "https://api.github.com/repos/seldrune-platform/seldrune-platform"
    ]


def test_github_app_missing_ids_is_configuration_not_invalid_secret(
    monkeypatch,
) -> None:
    def missing_config(_credential):
        raise provider_preflight.ToolGatewayError(
            "GitHub App id and installation id are required with the private key"
        )

    monkeypatch.setattr(
        provider_preflight,
        "_github_app_config",
        missing_config,
    )

    result = provider_preflight.preflight_provider_credential(
        "github",
        "-----BEGIN PRIVATE KEY-----\nredacted\n-----END PRIVATE KEY-----",
    )

    assert result["verified"] is False
    assert result["status"] == "configuration_error"
    assert result["http_status"] is None


def test_provider_preflight_reports_invalid_remote_credential(
    client,
    monkeypatch,
) -> None:
    monkeypatch.delenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", raising=False)
    monkeypatch.setenv("SELDRUNE_GITHUB_TOOL_TOKEN", "bad-github-token")
    monkeypatch.delenv("SELDRUNE_RENDER_API_KEY", raising=False)
    monkeypatch.delenv("SELDRUNE_CI_RECEIPT_HMAC_KEY", raising=False)

    def fake_get(url, *, headers, timeout):
        assert url == "https://api.github.com/user"
        assert headers["Authorization"] == "Bearer bad-github-token"
        return _response(401, json_data={"message": "Bad credentials"})

    monkeypatch.setattr(provider_preflight.httpx, "get", fake_get)

    token, organization_id = register_owner(client)
    headers = _headers(token)
    assert client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap",
        headers=headers,
        json={},
    ).status_code == 200

    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/preflight",
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()["providers"]}
    assert providers["github"]["status"] == "credential_invalid"
    assert providers["github"]["http_status"] == 401
    assert providers["gmail"]["status"] == "not_configured"
    assert providers["render"]["status"] == "not_configured"


def test_provider_preflight_handles_network_failure_without_leaking_secret(
    client,
    monkeypatch,
) -> None:
    monkeypatch.delenv("SELDRUNE_GMAIL_TOOL_CREDENTIAL", raising=False)
    monkeypatch.delenv("SELDRUNE_GITHUB_TOOL_TOKEN", raising=False)
    monkeypatch.setenv("SELDRUNE_RENDER_API_KEY", "render-network-secret")
    monkeypatch.delenv("SELDRUNE_CI_RECEIPT_HMAC_KEY", raising=False)

    def failing_get(url, *, headers, timeout):
        raise httpx.ConnectError(
            "provider offline",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(provider_preflight.httpx, "get", failing_get)

    token, organization_id = register_owner(client)
    headers = _headers(token)
    assert client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap",
        headers=headers,
        json={},
    ).status_code == 200

    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-bootstrap/preflight",
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    render = next(
        item
        for item in response.json()["providers"]
        if item["provider"] == "render"
    )
    assert render["status"] == "network_error"
    assert "render-network-secret" not in str(response.json())
