from uuid import uuid4

from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _invite_user(
    client,
    organization_id: str,
    owner_headers: dict[str, str],
    *,
    email: str,
    role: str,
) -> dict[str, str]:
    invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=owner_headers,
        json={"email": email, "role": role, "expires_in_hours": 24},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": invitation.json()["token"],
            "display_name": f"{role.title()} User",
            "password": f"{role}-password-123",
        },
    )
    assert accepted.status_code == 201
    return _headers(accepted.json()["access_token"])


def _create_reference(
    client,
    organization_id: str,
    headers: dict[str, str],
    *,
    slug: str,
    locator: str,
):
    return client.post(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
        json={
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "provider": "env",
            "locator": locator,
        },
    )


def test_secret_reference_registry_rbac_and_non_disclosure(client) -> None:
    owner_token, organization_id = register_owner(client)
    owner_headers = _headers(owner_token)

    created = _create_reference(
        client,
        organization_id,
        owner_headers,
        slug="openai-api",
        locator="OPENAI_API_KEY",
    )
    assert created.status_code == 201
    reference = created.json()
    assert reference["provider"] == "env"
    assert reference["locator"] == "OPENAI_API_KEY"
    assert reference["status"] == "active"
    assert "value" not in reference
    assert "secret" not in reference

    rejected_value = client.post(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=owner_headers,
        json={
            "name": "Rejected Secret",
            "slug": "rejected-secret",
            "provider": "env",
            "locator": "REJECTED_SECRET",
            "value": "must-not-be-accepted",
        },
    )
    assert rejected_value.status_code == 422

    invalid_locator = _create_reference(
        client,
        organization_id,
        owner_headers,
        slug="invalid-locator",
        locator="not-an-env-name",
    )
    assert invalid_locator.status_code == 400

    duplicate = _create_reference(
        client,
        organization_id,
        owner_headers,
        slug="openai-api",
        locator="OPENAI_API_KEY_2",
    )
    assert duplicate.status_code == 409

    listed = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=owner_headers,
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [reference["id"]]

    detail = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references/{reference['id']}",
        headers=owner_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == reference["id"]

    updated = client.patch(
        f"/api/v1/organizations/{organization_id}/secret-references/{reference['id']}",
        headers=owner_headers,
        json={
            "name": "OpenAI API Rotated",
            "locator": "OPENAI_API_KEY_V2",
            "status": "disabled",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "OpenAI API Rotated"
    assert updated.json()["locator"] == "OPENAI_API_KEY_V2"
    assert updated.json()["status"] == "disabled"

    null_update = client.patch(
        f"/api/v1/organizations/{organization_id}/secret-references/{reference['id']}",
        headers=owner_headers,
        json={"locator": None},
    )
    assert null_update.status_code == 400

    admin_headers = _invite_user(
        client,
        organization_id,
        owner_headers,
        email="secret-admin@example.com",
        role="admin",
    )
    member_headers = _invite_user(
        client,
        organization_id,
        owner_headers,
        email="secret-member@example.com",
        role="member",
    )
    auditor_headers = _invite_user(
        client,
        organization_id,
        owner_headers,
        email="secret-auditor@example.com",
        role="auditor",
    )

    assert (
        client.get(
            f"/api/v1/organizations/{organization_id}/secret-references",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/organizations/{organization_id}/secret-references",
            headers=member_headers,
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/organizations/{organization_id}/secret-references",
            headers=auditor_headers,
        ).status_code
        == 403
    )

    admin_reference = _create_reference(
        client,
        organization_id,
        admin_headers,
        slug="admin-managed",
        locator="ADMIN_MANAGED_SECRET",
    )
    assert admin_reference.status_code == 201
    deleted = client.delete(
        f"/api/v1/organizations/{organization_id}/secret-references/"
        f"{admin_reference.json()['id']}",
        headers=admin_headers,
    )
    assert deleted.status_code == 204

    foreign_org = uuid4()
    assert (
        client.get(
            f"/api/v1/organizations/{foreign_org}/secret-references/{reference['id']}",
            headers=owner_headers,
        ).status_code
        == 403
    )

    audit = client.get(
        f"/api/v1/organizations/{organization_id}/audit",
        headers=owner_headers,
        params={"resource_type": "secret_reference"},
    )
    assert audit.status_code == 200
    details = [item["details"] for item in audit.json()["items"]]
    assert details
    assert all("OPENAI_API_KEY" not in str(item) for item in details)
    assert all("ADMIN_MANAGED_SECRET" not in str(item) for item in details)


def test_secret_reference_delete_is_dependency_safe(client) -> None:
    owner_token, organization_id = register_owner(client)
    owner_headers = _headers(owner_token)

    research_reference = _create_reference(
        client,
        organization_id,
        owner_headers,
        slug="research-credential",
        locator="RESEARCH_CREDENTIAL",
    )
    assert research_reference.status_code == 201
    research_reference_id = research_reference.json()["id"]

    connector = client.post(
        f"/api/v1/organizations/{organization_id}/research/connectors",
        headers=owner_headers,
        json={
            "name": "Fixture Research",
            "slug": "fixture-research",
            "provider": "fixture",
            "secret_reference_id": research_reference_id,
            "config": {},
        },
    )
    assert connector.status_code == 201

    blocked_research_delete = client.delete(
        f"/api/v1/organizations/{organization_id}/secret-references/"
        f"{research_reference_id}",
        headers=owner_headers,
    )
    assert blocked_research_delete.status_code == 409

    disabled_research = client.patch(
        f"/api/v1/organizations/{organization_id}/secret-references/"
        f"{research_reference_id}",
        headers=owner_headers,
        json={"status": "disabled"},
    )
    assert disabled_research.status_code == 200
    assert disabled_research.json()["status"] == "disabled"

    webhook_reference = _create_reference(
        client,
        organization_id,
        owner_headers,
        slug="webhook-signing",
        locator="WEBHOOK_SIGNING_SECRET",
    )
    assert webhook_reference.status_code == 201
    webhook_reference_id = webhook_reference.json()["id"]

    endpoint = client.post(
        f"/api/v1/organizations/{organization_id}/webhooks",
        headers=owner_headers,
        json={
            "name": "Signed Events",
            "slug": "signed-events",
            "secret_reference_id": webhook_reference_id,
            "allowed_event_types": ["test.event"],
        },
    )
    assert endpoint.status_code == 201

    blocked_webhook_delete = client.delete(
        f"/api/v1/organizations/{organization_id}/secret-references/"
        f"{webhook_reference_id}",
        headers=owner_headers,
    )
    assert blocked_webhook_delete.status_code == 409

    disabled_webhook = client.patch(
        f"/api/v1/organizations/{organization_id}/secret-references/"
        f"{webhook_reference_id}",
        headers=owner_headers,
        json={"status": "disabled"},
    )
    assert disabled_webhook.status_code == 200
    assert disabled_webhook.json()["status"] == "disabled"


def test_secret_reference_delete_blocks_tool_dependency(client) -> None:
    owner_token, organization_id = register_owner(client)
    owner_headers = _headers(owner_token)

    reference = _create_reference(
        client,
        organization_id,
        owner_headers,
        slug="github-token",
        locator="GITHUB_TOOL_TOKEN",
    )
    assert reference.status_code == 201
    reference_id = reference.json()["id"]

    tool = client.post(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=owner_headers,
        json={
            "name": "GitHub Issue",
            "slug": "github-issue",
            "provider": "github",
            "action_name": "create-issue",
            "credential_reference_id": reference_id,
            "risk_level": "medium",
        },
    )
    assert tool.status_code == 201

    deleted = client.delete(
        f"/api/v1/organizations/{organization_id}/secret-references/{reference_id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 409
