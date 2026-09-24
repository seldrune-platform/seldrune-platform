import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import models  # noqa: F401
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.development_mission import build_development_mission


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
            "email": "mission-owner@example.com",
            "password": "correct horse battery staple",
            "display_name": "Mission Owner",
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


def test_development_mission_calculates_evidence_weighted_progress() -> None:
    mission = build_development_mission()
    workstreams = {
        item["id"]: item for item in mission["workstreams"]
    }

    assert mission["version"] == "cognitive-execution-v2"
    assert mission["overall_percentage"] == 61.0
    assert mission["remaining_percentage"] == 39.0
    assert workstreams["unarchi"]["percentage"] == 75.0
    assert workstreams["console"]["percentage"] == 90.0
    assert workstreams["live_media"]["percentage"] == 25.0
    assert workstreams["live_media"]["paused"] is True
    assert set(mission["parallel_ready_stage_ids"]) == {
        "unarchi_v31",
        "model_router_unified",
        "pdf_local_labels",
        "provider_connectors",
    }
    assert "live_face_runtime" in mission["paused_stage_ids"]
    assert mission["execution_policy"]["single_go_intent"] is True
    assert mission["execution_policy"]["dependency_guard"] is True
    assert mission["execution_policy"]["auto_execute_external_actions"] is False


def test_mission_sync_persists_one_master_and_queues_ready_wave(
    client: TestClient,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first = client.post(
        f"{base}/development-mission/sync",
        headers=headers,
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["created"] is True
    assert payload["overall_percentage"] == 61.0
    assert payload["auto_queued_count"] == 4
    assert set(payload["auto_queued_stage_ids"]) == {
        "unarchi_v31",
        "model_router_unified",
        "pdf_local_labels",
        "provider_connectors",
    }

    second = client.post(
        f"{base}/development-mission/sync",
        headers=headers,
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["master_task_id"] == payload["master_task_id"]
    assert second_payload["auto_queued_count"] == 0

    tasks = client.get(f"{base}/tasks", headers=headers)
    assert tasks.status_code == 200
    rows = tasks.json()
    master = [
        item
        for item in rows
        if item["title"] == "Seldrune Master Development Mission"
    ]
    assert len(master) == 1
    assert master[0]["status"] == "queued"
    assert master[0]["input_data"]["mission_version"] == "cognitive-execution-v2"

    stages = [
        item
        for item in rows
        if item["input_data"].get("cognitive_mission_stage_id")
    ]
    assert len(stages) == 4
    assert not any(
        item["input_data"].get("workstream") == "live_media"
        for item in stages
    )


def test_mission_queue_ready_is_idempotent(client: TestClient) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    synchronized = client.post(
        f"{base}/development-mission/sync",
        headers=headers,
    )
    assert synchronized.status_code == 200

    queued = client.post(
        f"{base}/development-mission/queue-ready",
        headers=headers,
    )
    assert queued.status_code == 200
    assert queued.json()["queued_count"] == 0
    assert set(queued.json()["ready_stage_ids"]) == {
        "unarchi_v31",
        "model_router_unified",
        "pdf_local_labels",
        "provider_connectors",
    }


def test_owner_console_contains_cognitive_mission_board() -> None:
    with TestClient(app) as client:
        page = client.get("/console")
        assert page.status_code == 200
        assert "COGNITIVE EXECUTION · MASTER DEVELOPMENT TASK" in page.text
        assert "cognitive-mission" in page.text
        assert "mission-overall" in page.text
        assert "mission-ready-stages" in page.text
        assert "Queue ready wave" in page.text
        assert "/console-assets/cognitive-mission.css" in page.text
        assert "/console-assets/cognitive-mission.js" in page.text

        script = client.get("/console-assets/cognitive-mission.js")
        assert script.status_code == 200
        assert "/development-mission/sync" in script.text
        assert "/development-mission/queue-ready" in script.text
        assert "Synchronized" in script.text
