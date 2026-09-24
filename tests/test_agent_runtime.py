import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import models  # noqa: F401
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app


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


def register_owner(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "runtime-founder@example.com",
            "password": "correct horse battery staple",
            "display_name": "Runtime Founder",
            "organization_name": "Seldrune Runtime",
            "organization_slug": "seldrune-runtime",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    profile = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    organization_id = profile["memberships"][0]["organization"]["id"]
    return token, organization_id


def create_runtime_task(
    client: TestClient,
    token: str,
    organization_id: str,
    *,
    agent_overrides: dict | None = None,
    task_input_data: dict | None = None,
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    agent_payload = {
        "name": "R&D Runtime Agent",
        "slug": "rnd-runtime-agent",
        "description": "Executes research tasks.",
        "capabilities": ["research", "analysis"],
        "runtime_config": {
            "provider": "mock",
            "model": "mock-v1",
            "input_cost_per_million": 1.0,
            "output_cost_per_million": 2.0,
        },
    }
    if agent_overrides:
        agent_payload.update(agent_overrides)
    agent_response = client.post(
        f"/api/v1/organizations/{organization_id}/agents",
        headers=headers,
        json=agent_payload,
    )
    assert agent_response.status_code == 201
    agent = agent_response.json()

    task_response = client.post(
        f"/api/v1/organizations/{organization_id}/tasks",
        headers=headers,
        json={
            "title": "Validate reconciliation pain",
            "objective": "Find evidence that payment reconciliation is painful.",
            "priority": 20,
            "input_data": (
                {"market": "India"}
                if task_input_data is None
                else task_input_data
            ),
            "assigned_agent_id": agent["id"],
        },
    )
    assert task_response.status_code == 201
    return task_response.json()


def test_mock_agent_runtime_executes_task_and_records_usage(client: TestClient) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = create_runtime_task(client, token, organization_id)

    execute = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/execute",
        headers=headers,
    )
    assert execute.status_code == 200
    completed = execute.json()
    assert completed["status"] == "succeeded"
    assert completed["output_data"]["provider"] == "mock"
    assert completed["output_data"]["model"] == "mock-v1"
    assert completed["output_data"]["agent_version"] == 1
    assert completed["output_data"]["usage"]["total_tokens"] > 0
    assert "payment reconciliation" in completed["output_data"]["text"].lower()

    invocations = client.get(
        f"/api/v1/organizations/{organization_id}/model-invocations",
        headers=headers,
    )
    assert invocations.status_code == 200
    invocation = invocations.json()[0]
    assert invocation["status"] == "succeeded"
    assert invocation["provider"] == "mock"
    assert invocation["total_tokens"] > 0
    assert invocation["estimated_cost_usd"] is not None

    events = client.get(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/events",
        headers=headers,
    )
    assert events.status_code == 200
    event_types = [event["event_type"] for event in events.json()]
    assert "agent.runtime.started" in event_types
    assert "agent.runtime.completed" in event_types


def test_structured_agent_runtime_rejects_invalid_mock_json(
    client: TestClient,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = create_runtime_task(
        client,
        token,
        organization_id,
        task_input_data={
            "model_response_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                },
                "required": ["result"],
                "additionalProperties": False,
            }
        },
    )

    execute = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/execute",
        headers=headers,
    )
    assert execute.status_code == 502
    assert "Structured model output was not valid JSON" in execute.json()["detail"]

    failed = client.get(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}",
        headers=headers,
    )
    assert failed.status_code == 200
    payload = failed.json()
    assert payload["status"] == "failed"
    assert payload["output_data"]["response_schema_applied"] is True
    assert payload["output_data"]["structured_output"] is None
    assert (
        payload["output_data"]["structured_output_error"]
        == "Structured model output was not valid JSON"
    )

    invocations = client.get(
        f"/api/v1/organizations/{organization_id}/model-invocations",
        headers=headers,
    )
    assert invocations.status_code == 200
    assert invocations.json()[0]["status"] == "succeeded"

    events = client.get(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/events",
        headers=headers,
    )
    assert events.status_code == 200
    assert "agent.runtime.structured_output_failed" in {
        event["event_type"] for event in events.json()
    }


def test_agent_model_policy_allows_configured_runtime(client: TestClient) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = create_runtime_task(
        client,
        token,
        organization_id,
        agent_overrides={
            "allowed_model_providers": ["mock"],
            "allowed_models": ["mock-v1"],
        },
    )

    execute = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/execute",
        headers=headers,
    )
    assert execute.status_code == 200
    assert execute.json()["output_data"]["agent_version"] == 1


@pytest.mark.parametrize(
    ("agent_overrides", "detail_fragment"),
    [
        (
            {"allowed_model_providers": ["openai"]},
            "Model provider 'mock' is not allowed",
        ),
        (
            {
                "allowed_model_providers": ["mock"],
                "allowed_models": ["different-model"],
            },
            "Model 'mock-v1' is not allowed",
        ),
    ],
)
def test_agent_model_policy_blocks_before_invocation(
    client: TestClient,
    agent_overrides: dict,
    detail_fragment: str,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = create_runtime_task(
        client,
        token,
        organization_id,
        agent_overrides=agent_overrides,
    )

    execute = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/execute",
        headers=headers,
    )
    assert execute.status_code == 409
    assert detail_fragment in execute.json()["detail"]

    unchanged_task = client.get(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}",
        headers=headers,
    )
    assert unchanged_task.status_code == 200
    assert unchanged_task.json()["status"] == "assigned"

    invocations = client.get(
        f"/api/v1/organizations/{organization_id}/model-invocations",
        headers=headers,
    )
    assert invocations.status_code == 200
    assert invocations.json() == []


def test_unassigned_task_cannot_execute(client: TestClient) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    task_response = client.post(
        f"/api/v1/organizations/{organization_id}/tasks",
        headers=headers,
        json={
            "title": "Unassigned task",
            "objective": "Wait for a matching agent.",
            "input_data": {},
        },
    )
    assert task_response.status_code == 201

    execute = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task_response.json()['id']}/execute",
        headers=headers,
    )
    assert execute.status_code == 409
