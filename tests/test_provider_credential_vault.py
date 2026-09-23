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
