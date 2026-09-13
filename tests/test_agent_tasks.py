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
            "email": "owner@example.com",
            "password": "correct horse battery staple",
            "display_name": "Owner",
            "organization_name": "Seldrune",
            "organization_slug": "seldrune",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["memberships"][0]["organization"]["id"]
    return token, organization_id


def test_agent_registry_and_task_lifecycle(client: TestClient) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    agent_response = client.post(
        f"/api/v1/organizations/{organization_id}/agents",
        headers=headers,
        json={
            "name": "R&D Agent",
            "slug": "rnd-agent",
            "description": "Researches markets and validates opportunities.",
            "capabilities": ["research", "analysis", "experiments"],
            "runtime_config": {"model_class": "reasoning"},
        },
    )
    assert agent_response.status_code == 201
    agent = agent_response.json()
    assert agent["status"] == "active"

    task_response = client.post(
        f"/api/v1/organizations/{organization_id}/tasks",
        headers=headers,
        json={
            "title": "Find reconciliation pain",
            "objective": "Research payment reconciliation problems and evidence.",
            "priority": 20,
            "input_data": {"market": "India"},
            "assigned_agent_id": agent["id"],
        },
    )
    assert task_response.status_code == 201
    task = task_response.json()
    assert task["status"] == "assigned"

    running = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/transition",
        headers=headers,
        json={"status": "running"},
    )
    assert running.status_code == 200
    assert running.json()["started_at"] is not None

    completed = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/transition",
        headers=headers,
        json={
            "status": "succeeded",
            "output_data": {"pain_score": 86, "recommendation": "prototype"},
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "succeeded"
    assert completed.json()["output_data"]["pain_score"] == 86

    events = client.get(
        f"/api/v1/organizations/{organization_id}/tasks/{task['id']}/events",
        headers=headers,
    )
    assert events.status_code == 200
    event_types = [event["event_type"] for event in events.json()]
    assert event_types == [
        "task.created",
        "task.status_changed",
        "task.status_changed",
    ]


def test_invalid_task_transition_returns_conflict(client: TestClient) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    task_response = client.post(
        f"/api/v1/organizations/{organization_id}/tasks",
        headers=headers,
        json={
            "title": "Queued research",
            "objective": "Wait for an agent assignment.",
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    invalid = client.post(
        f"/api/v1/organizations/{organization_id}/tasks/{task_id}/transition",
        headers=headers,
        json={"status": "succeeded", "output_data": {"unexpected": True}},
    )
    assert invalid.status_code == 409
