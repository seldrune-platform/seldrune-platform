import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import models  # noqa: F401
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.tool_gateway import register_external_action


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def register_owner(client: TestClient) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "tools-founder@example.com",
            "password": "correct horse battery staple",
            "display_name": "Tools Founder",
            "organization_name": "Seldrune Tools",
            "organization_slug": "seldrune-tools",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["memberships"][0]["organization"]["id"]
    return headers, organization_id


def create_tool(
    client: TestClient,
    headers: dict[str, str],
    organization_id: str,
    *,
    slug: str,
    action_name: str,
    risk_level: str = "low",
    approval_mode: str = "never",
    provider: str = "internal",
) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
        json={
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "provider": provider,
            "action_name": action_name,
            "risk_level": risk_level,
            "approval_mode": approval_mode,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_low_risk_tool_runs_immediately(client: TestClient) -> None:
    headers, organization_id = register_owner(client)
    tool = create_tool(
        client,
        headers,
        organization_id,
        slug="echo-tool",
        action_name="echo",
    )
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={"tool_id": tool["id"], "input_data": {"message": "hello"}},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output_data"] == {"echo": {"message": "hello"}}


def test_high_risk_tool_requires_approval(client: TestClient) -> None:
    headers, organization_id = register_owner(client)
    tool = create_tool(
        client,
        headers,
        organization_id,
        slug="reviewed-text-stats",
        action_name="text-stats",
        risk_level="high",
        approval_mode="never",
    )
    assert tool["approval_mode"] == "always"

    requested = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={"tool_id": tool["id"], "input_data": {"text": "one two three"}},
    )
    assert requested.status_code == 201
    pending = requested.json()
    assert pending["status"] == "pending_approval"
    assert pending["output_data"] is None

    approved = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs/{pending['id']}/approve",
        headers=headers,
        json={},
    )
    assert approved.status_code == 200
    completed = approved.json()
    assert completed["status"] == "succeeded"
    assert completed["output_data"]["words"] == 3


def test_unknown_internal_action_is_rejected(client: TestClient) -> None:
    headers, organization_id = register_owner(client)
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
        json={
            "name": "Unknown Tool",
            "slug": "unknown-tool",
            "action_name": "not-registered",
        },
    )
    assert response.status_code == 422


def test_external_provider_requires_registered_adapter(client: TestClient) -> None:
    headers, organization_id = register_owner(client)
    tool = create_tool(
        client,
        headers,
        organization_id,
        slug="missing-adapter",
        provider="example",
        action_name="send",
    )
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={"tool_id": tool["id"], "input_data": {"message": "hello"}},
    )
    assert response.status_code == 409
    assert "adapter is not registered" in response.json()["detail"]


def test_external_provider_requires_execution_receipt(client: TestClient) -> None:
    register_external_action(
        "example-no-evidence",
        "send",
        lambda payload, credential: {"sent": True},
    )
    headers, organization_id = register_owner(client)
    tool = create_tool(
        client,
        headers,
        organization_id,
        slug="no-evidence",
        provider="example-no-evidence",
        action_name="send",
    )
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={"tool_id": tool["id"], "input_data": {"message": "hello"}},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "failed"
    assert "receipt_id" in run["error_message"]


def test_external_provider_succeeds_with_execution_receipt(client: TestClient) -> None:
    register_external_action(
        "example-evidence",
        "send",
        lambda payload, credential: {
            "sent": True,
            "evidence": {"receipt_id": "provider-message-123"},
        },
    )
    headers, organization_id = register_owner(client)
    tool = create_tool(
        client,
        headers,
        organization_id,
        slug="evidence-backed",
        provider="example-evidence",
        action_name="send",
    )
    response = client.post(
        f"/api/v1/organizations/{organization_id}/tool-runs",
        headers=headers,
        json={"tool_id": tool["id"], "input_data": {"message": "hello"}},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "succeeded"
    assert run["output_data"]["evidence"]["receipt_id"] == "provider-message-123"
