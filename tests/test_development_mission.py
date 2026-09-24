from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import models  # noqa: F401
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.task import Task
from backend.app.services.development_mission import build_development_mission


@pytest.fixture
def session_factory():
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
    yield testing_session
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(session_factory) -> TestClient:
    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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

    unarchi = next(
        item
        for item in stages
        if item["input_data"]["cognitive_mission_stage_id"] == "unarchi_v31"
    )
    contract = unarchi["input_data"]["compiled_execution_contract"]
    assert contract["version"] == "stage-compiler-v1"
    assert contract["stage_id"] == "unarchi_v31"
    assert contract["profile"] == "repository-engineering"
    assert contract["executable_now"] is False
    assert contract["evidence_contract"] == {
        "model_output_is_completion_evidence": False,
        "completion_requires_machine_evidence": True,
        "all_tool_acceptance_checks_required": True,
    }
    assert "tool_unavailable:github:repository-info" in contract["blocking_reasons"]
    assert [step["id"] for step in contract["steps"]] == [
        "produce-artifacts",
        "inspect-repository",
        "create-stage-branch",
        "write-artifacts",
        "open-pull-request",
        "run-ci",
        "verify-ci",
    ]


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
        assert "Run One-Go" in page.text
        assert "ONE-GO EXECUTION CONTROLLER" in page.text
        assert "/console-assets/cognitive-mission.css" in page.text
        assert "/console-assets/cognitive-mission.js" in page.text

        script = client.get("/console-assets/cognitive-mission.js")
        assert script.status_code == 200
        assert "/development-mission/sync" in script.text
        assert "/development-mission/queue-ready" in script.text
        assert "/development-mission/execute" in script.text
        assert "runOneGo" in script.text
        assert "Synchronized" in script.text


def create_mission_agent(
    client: TestClient,
    headers: dict[str, str],
    organization_id: str,
) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/agents",
        headers=headers,
        json={
            "name": "Cognitive Execution Agent",
            "slug": "cognitive-execution-agent",
            "description": "Executes dependency-ready cognitive mission tasks.",
            "capabilities": [
                "reasoning",
                "validation",
                "engineering",
                "models",
                "integrations",
                "documents",
            ],
            "runtime_config": {
                "provider": "mock",
                "model": "mock-v1",
                "input_cost_per_million": 1.0,
                "output_cost_per_million": 2.0,
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def test_one_go_executes_model_work_without_faking_completion(
    client: TestClient,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    synchronized = client.post(
        f"{base}/development-mission/sync",
        headers=headers,
    )
    assert synchronized.status_code == 200
    create_mission_agent(client, headers, organization_id)

    executed = client.post(
        f"{base}/development-mission/execute",
        headers=headers,
        json={"max_waves": 3, "max_tasks": 8},
    )
    assert executed.status_code == 200
    report = executed.json()
    assert report["controller_version"] == "one-go-v1"
    assert report["starting_percentage"] == 61.0
    assert report["ending_percentage"] == 61.0
    assert report["waves_executed"] == 1
    assert report["tasks_executed"] == 3
    assert report["tasks_verified"] == 0
    assert report["tasks_unverified"] == 3
    assert report["tasks_blocked"] == 1
    assert report["tasks_failed"] == 0
    assert report["halted_reason"] == "no_new_verified_dependency_progress"

    by_stage = {
        item["stage_id"]: item
        for item in report["stage_results"]
    }
    assert by_stage["pdf_local_labels"]["disposition"] == "blocked"
    assert (
        by_stage["pdf_local_labels"]["reason"]
        == "owner-gated_requires_explicit_execution"
    )
    assert by_stage["unarchi_v31"]["disposition"] == "unverified"
    assert (
        by_stage["unarchi_v31"]["reason"]
        == "task_has_no_verifiable_tool_contract"
    )
    assert by_stage["unarchi_v31"]["compiled_contract_version"] == "stage-compiler-v1"
    assert by_stage["unarchi_v31"]["compiled_profile"] == "repository-engineering"
    assert by_stage["unarchi_v31"]["compiled_executable_now"] is False
    assert by_stage["unarchi_v31"]["compiled_blocking_reasons"]

    mission = client.get(
        f"{base}/development-mission",
        headers=headers,
    )
    assert mission.status_code == 200
    assert mission.json()["overall_percentage"] == 61.0
    assert mission.json()["one_go_execution"]["tasks_verified"] == 0


def test_one_go_verified_tool_receipt_unlocks_next_dependency(
    client: TestClient,
    session_factory,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    synchronized = client.post(
        f"{base}/development-mission/sync",
        headers=headers,
    )
    assert synchronized.status_code == 200
    agent = create_mission_agent(client, headers, organization_id)

    tasks = client.get(f"{base}/tasks", headers=headers)
    assert tasks.status_code == 200
    unarchi = next(
        item
        for item in tasks.json()
        if item["input_data"].get("cognitive_mission_stage_id") == "unarchi_v31"
    )
    assigned = client.post(
        f"{base}/tasks/{unarchi['id']}/assign",
        headers=headers,
        json={"agent_id": agent["id"]},
    )
    assert assigned.status_code == 200

    tool = client.post(
        f"{base}/tools",
        headers=headers,
        json={
            "name": "Mission Evidence Echo",
            "slug": "mission-evidence-echo",
            "provider": "internal",
            "action_name": "echo",
            "risk_level": "low",
            "approval_mode": "never",
        },
    )
    assert tool.status_code == 201

    with session_factory() as session:
        task = session.get(Task, UUID(unarchi["id"]))
        assert task is not None
        task.input_data = {
            **(task.input_data or {}),
            "tool_request": {
                "slug": "mission-evidence-echo",
                "input": {"message": "verified mission evidence"},
            },
        }
        session.commit()

    tool_run = client.post(
        f"{base}/tool-runs",
        headers=headers,
        json={
            "tool_id": tool.json()["id"],
            "task_id": unarchi["id"],
            "input_data": {"message": "verified mission evidence"},
        },
    )
    assert tool_run.status_code == 201
    run = tool_run.json()
    assert run["status"] == "succeeded"

    running = client.post(
        f"{base}/tasks/{unarchi['id']}/transition",
        headers=headers,
        json={"status": "running"},
    )
    assert running.status_code == 200
    succeeded = client.post(
        f"{base}/tasks/{unarchi['id']}/transition",
        headers=headers,
        json={
            "status": "succeeded",
            "output_data": {
                "execution_type": "tool",
                "tool_slug": "mission-evidence-echo",
                "evidence": {
                    "receipt_id": f"tool-run:{run['id']}",
                    "tool_run_id": run["id"],
                },
            },
        },
    )
    assert succeeded.status_code == 200

    executed = client.post(
        f"{base}/development-mission/execute",
        headers=headers,
        json={"max_waves": 1, "max_tasks": 1},
    )
    assert executed.status_code == 200
    report = executed.json()
    assert report["tasks_verified"] == 1
    assert report["tasks_unverified"] == 0
    assert report["ending_percentage"] == 61.9
    assert report["stage_results"][0]["stage_id"] == "unarchi_v31"
    assert report["stage_results"][0]["disposition"] == "verified"
    assert report["stage_results"][0]["reason"] == "verified_tool_receipt"

    mission = client.get(
        f"{base}/development-mission",
        headers=headers,
    )
    assert mission.status_code == 200
    payload = mission.json()
    assert payload["overall_percentage"] == 61.9
    stages = {
        item["id"]: item
        for item in payload["stages"]
    }
    assert stages["unarchi_v31"]["status"] == "completed"
    assert stages["unarchi_v31"]["completion_source"] == "runtime_verified"
    assert stages["unarchi_v32"]["ready"] is True
    assert "unarchi_v32" in payload["parallel_ready_stage_ids"]


def test_one_go_respects_autonomous_execution_governance(
    client: TestClient,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"
    synchronized = client.post(
        f"{base}/development-mission/sync",
        headers=headers,
    )
    assert synchronized.status_code == 200
    create_mission_agent(client, headers, organization_id)

    policy = client.put(
        f"{base}/governance-policy",
        headers=headers,
        json={
            "max_steps_per_command": 25,
            "max_project_budget_usd": 100.0,
            "allow_autonomous_execution": False,
        },
    )
    assert policy.status_code == 200

    executed = client.post(
        f"{base}/development-mission/execute",
        headers=headers,
        json={"max_waves": 3, "max_tasks": 8},
    )
    assert executed.status_code == 200
    report = executed.json()
    assert report["governance"]["autonomous_execution_allowed"] is False
    assert report["waves_executed"] == 0
    assert report["tasks_executed"] == 0
    assert report["tasks_verified"] == 0
    assert report["halted_reason"] == "governance_autonomous_execution_disabled"
