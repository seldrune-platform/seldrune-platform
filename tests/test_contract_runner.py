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
from backend.app.services import contract_runner


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
            "email": "contract-owner@example.com",
            "password": "correct horse battery staple",
            "display_name": "Contract Owner",
            "organization_name": "Contract Seldrune",
            "organization_slug": "contract-seldrune",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["memberships"][0]["organization"]["id"]
    return token, organization_id


def create_agent(
    client: TestClient,
    headers: dict[str, str],
    organization_id: str,
) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/agents",
        headers=headers,
        json={
            "name": "Contract Agent",
            "slug": "contract-agent",
            "description": "Executes persisted compiled contracts.",
            "capabilities": ["engineering", "validation"],
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


def test_contract_preflight_blocks_before_model_cost(
    client: TestClient,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    task = client.post(
        f"/api/v1/organizations/{organization_id}/tasks",
        headers=headers,
        json={
            "title": "Blocked compiled stage",
            "objective": "Do not spend model tokens until tools exist.",
            "input_data": {
                "cognitive_mission_stage_id": "blocked-test-stage",
                "required_capabilities": ["engineering"],
                "compiled_execution_contract": {
                    "version": "stage-compiler-v1",
                    "execution_mode": "automatic",
                    "steps": [
                        {
                            "id": "produce-artifacts",
                            "kind": "model",
                            "response_schema": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                        },
                        {
                            "id": "missing-tool",
                            "kind": "tool",
                            "provider": "github",
                            "action_name": "repository-info",
                            "tool_slug": None,
                            "input": {},
                            "bindings": {},
                            "missing_fields": [],
                            "acceptance": {"receipt_required": True},
                        },
                    ],
                },
            },
        },
    )
    assert task.status_code == 201

    advanced = client.post(
        (
            f"/api/v1/organizations/{organization_id}/development-mission/"
            f"tasks/{task.json()['id']}/advance-contract"
        ),
        headers=headers,
        json={"max_steps": 5},
    )
    assert advanced.status_code == 200
    report = advanced.json()
    assert report["status"] == "blocked"
    assert report["reason"] == "compiled_tools_unavailable:missing-tool"
    assert report["executed_steps"] == 0

    invocations = client.get(
        f"/api/v1/organizations/{organization_id}/model-invocations",
        headers=headers,
    )
    assert invocations.status_code == 200
    assert invocations.json() == []

    recovered = client.post(
        (
            f"/api/v1/organizations/{organization_id}/development-mission/"
            f"tasks/{task.json()['id']}/recover-contract"
        ),
        headers=headers,
        json={"max_steps": 5, "max_rounds": 5},
    )
    assert recovered.status_code == 200
    recovery = recovered.json()["recovery"]
    assert recovery["rounds_executed"] == 1
    assert recovery["final_classification"] == "configuration"
    assert recovery["requires_configuration"] is True


def test_contract_runner_verifies_receipts_and_detects_tampering(
    client: TestClient,
    session_factory,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    agent = create_agent(client, headers, organization_id)

    tool_response = client.post(
        f"/api/v1/organizations/{organization_id}/tools",
        headers=headers,
        json={
            "name": "Contract Echo",
            "slug": "contract-echo",
            "provider": "internal",
            "action_name": "echo",
            "risk_level": "low",
            "approval_mode": "never",
        },
    )
    assert tool_response.status_code == 201
    tool = tool_response.json()

    contract = {
        "version": "stage-compiler-v1",
        "execution_mode": "automatic",
        "steps": [
            {
                "id": "produce-artifacts",
                "kind": "model",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "artifacts": {"type": "array"},
                    },
                    "required": ["artifacts"],
                },
            },
            {
                "id": "echo-evidence",
                "kind": "tool",
                "provider": "internal",
                "action_name": "echo",
                "tool_slug": tool["slug"],
                "tool_id": tool["id"],
                "input": {"message": "verified contract evidence"},
                "bindings": {},
                "missing_fields": [],
                "acceptance": {"receipt_required": True},
            },
        ],
    }
    parent_response = client.post(
        f"/api/v1/organizations/{organization_id}/tasks",
        headers=headers,
        json={
            "title": "Executable compiled stage",
            "objective": "Complete only from persisted machine evidence.",
            "priority": 90,
            "assigned_agent_id": agent["id"],
            "input_data": {
                "cognitive_mission_stage_id": "contract-test-stage",
                "required_capabilities": ["engineering"],
                "compiled_execution_contract": contract,
            },
        },
    )
    assert parent_response.status_code == 201
    parent = parent_response.json()

    with session_factory() as session:
        persisted_parent = session.get(Task, UUID(parent["id"]))
        assert persisted_parent is not None
        model_child = Task(
            organization_id=UUID(organization_id),
            created_by_user_id=persisted_parent.created_by_user_id,
            assigned_agent_id=UUID(agent["id"]),
            title="Executable compiled stage · produce-artifacts",
            objective="Produce a validated artifact.",
            priority=90,
            status="succeeded",
            input_data={
                "contract_parent_task_id": parent["id"],
                "contract_step_id": "produce-artifacts",
                "contract_step_attempt": 1,
                "contract_repeat_index": None,
            },
            output_data={
                "response_schema_applied": True,
                "structured_output": {
                    "artifacts": [
                        {
                            "path": "docs/contract-proof.txt",
                            "content": "verified",
                            "message": "test: add contract proof",
                        }
                    ]
                },
            },
        )
        session.add(model_child)
        session.commit()

    advanced = client.post(
        (
            f"/api/v1/organizations/{organization_id}/development-mission/"
            f"tasks/{parent['id']}/advance-contract"
        ),
        headers=headers,
        json={"max_steps": 5},
    )
    assert advanced.status_code == 200
    report = advanced.json()
    assert report["status"] == "verified"
    assert report["verified"] is True
    assert report["executed_steps"] == 1
    assert any(
        ref.startswith("receipt:contract-chain:")
        for ref in report["evidence_refs"]
    )
    assert any(
        item["step_id"] == "echo-evidence"
        and item["status"] == "accepted"
        for item in report["step_results"]
    )

    completed = client.get(
        f"/api/v1/organizations/{organization_id}/tasks/{parent['id']}",
        headers=headers,
    )
    assert completed.status_code == 200
    payload = completed.json()
    assert payload["status"] == "succeeded"
    assert payload["output_data"]["execution_type"] == "compiled-contract"
    assert (
        payload["output_data"]["cognitive_verification"]["status"]
        == "verified"
    )

    with session_factory() as session:
        persisted_parent = session.get(Task, UUID(parent["id"]))
        assert persisted_parent is not None
        tampered = dict(persisted_parent.output_data or {})
        tampered["evidence"] = {"receipt_id": "contract-chain:tampered"}
        persisted_parent.output_data = tampered
        session.commit()

    rechecked = client.post(
        (
            f"/api/v1/organizations/{organization_id}/development-mission/"
            f"tasks/{parent['id']}/advance-contract"
        ),
        headers=headers,
        json={"max_steps": 5},
    )
    assert rechecked.status_code == 200
    second_report = rechecked.json()
    assert second_report["status"] == "unverified"
    assert second_report["verified"] is False
    assert second_report["reason"] == "compiled_contract_chain_receipt_mismatch"

def test_portable_ci_fallback_bindings_are_exact_and_coalesced() -> None:
    parent = Task(
        input_data={
            "portable_ci_evidence": {
                "receipt": {
                    "version": "seldrune-ci-v1",
                    "status": "success",
                    "release_sha": "portable-sha",
                },
                "signature": "sha256=signed",
            }
        }
    )
    fallback_step = {
        "input": {},
        "bindings": {
            "receipt": "parent.input.portable_ci_evidence.receipt",
            "signature": "parent.input.portable_ci_evidence.signature",
        },
        "missing_fields": [],
    }
    payload, unresolved = contract_runner._tool_payload(
        fallback_step,
        artifact=None,
        outputs={},
        parent_task=parent,
    )
    assert unresolved == []
    assert payload == parent.input_data["portable_ci_evidence"]

    merge_step = {
        "input": {},
        "bindings": {
            "sha": [
                "steps.verify-ci.output.head_sha",
                "steps.verify-portable-ci.output.head_sha",
            ]
        },
        "missing_fields": [],
    }
    payload, unresolved = contract_runner._tool_payload(
        merge_step,
        artifact=None,
        outputs={
            "verify-portable-ci": {"head_sha": "portable-sha"},
        },
        parent_task=parent,
    )
    assert unresolved == []
    assert payload == {"sha": "portable-sha"}

    payload, unresolved = contract_runner._tool_payload(
        merge_step,
        artifact=None,
        outputs={
            "verify-ci": {"head_sha": "github-sha"},
            "verify-portable-ci": {"head_sha": "portable-sha"},
        },
        parent_task=parent,
    )
    assert unresolved == []
    assert payload == {"sha": "github-sha"}


def test_optional_fallback_tool_does_not_satisfy_machine_evidence_alone(
    client: TestClient,
) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    agent = create_agent(client, headers, organization_id)

    task = client.post(
        f"/api/v1/organizations/{organization_id}/tasks",
        headers=headers,
        json={
            "title": "Fallback-only compiled stage",
            "objective": "Never verify from a skipped optional fallback.",
            "assigned_agent_id": agent["id"],
            "input_data": {
                "cognitive_mission_stage_id": "fallback-only-stage",
                "required_capabilities": ["engineering"],
                "compiled_execution_contract": {
                    "version": "stage-compiler-v1",
                    "execution_mode": "automatic",
                    "steps": [
                        {
                            "id": "verify-portable-ci",
                            "kind": "tool",
                            "provider": "portable-ci",
                            "action_name": "verify-receipt",
                            "tool_slug": None,
                            "tool_id": None,
                            "optional": True,
                            "run_when_external_resource_from": "verify-ci",
                            "input": {},
                            "bindings": {},
                            "missing_fields": [],
                            "acceptance": {"receipt_required": True},
                        }
                    ],
                },
            },
        },
    )
    assert task.status_code == 201

    advanced = client.post(
        (
            f"/api/v1/organizations/{organization_id}/development-mission/"
            f"tasks/{task.json()['id']}/advance-contract"
        ),
        headers=headers,
        json={"max_steps": 3},
    )
    assert advanced.status_code == 200
    report = advanced.json()
    assert report["status"] == "blocked"
    assert report["reason"] == "fallback_source_missing:verify-ci"
    assert report["verified"] is False

