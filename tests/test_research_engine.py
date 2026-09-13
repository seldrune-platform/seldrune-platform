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


def register_owner(client: TestClient) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "research-founder@example.com",
            "password": "correct horse battery staple",
            "display_name": "Research Founder",
            "organization_name": "Seldrune Research",
            "organization_slug": "seldrune-research",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile = client.get("/api/v1/auth/me", headers=headers).json()
    organization_id = profile["memberships"][0]["organization"]["id"]
    return headers, organization_id


def test_fixture_research_ingests_provenance_into_knowledge(client: TestClient) -> None:
    headers, organization_id = register_owner(client)
    connector = client.post(
        f"/api/v1/organizations/{organization_id}/research/connectors",
        headers=headers,
        json={
            "name": "Research Fixture",
            "slug": "research-fixture",
            "provider": "fixture",
            "config": {
                "documents": [
                    {
                        "title": "Payment reconciliation market evidence",
                        "content": (
                            "Payment reconciliation teams compare gateway settlements, "
                            "bank credits, refunds, and ERP records."
                        ),
                        "uri": "fixture://payments/reconciliation",
                        "source_type": "fixture-report",
                    },
                    {
                        "title": "Unrelated logistics note",
                        "content": "Warehouse routing and fleet utilization.",
                        "uri": "fixture://logistics/routing",
                    },
                ]
            },
        },
    )
    assert connector.status_code == 201

    research_session = client.post(
        f"/api/v1/organizations/{organization_id}/research/sessions",
        headers=headers,
        json={
            "title": "Reconciliation opportunity research",
            "query": "payment reconciliation automation",
            "objective": "Find evidence for a reconciliation product opportunity.",
            "connector_ids": [connector.json()["id"]],
        },
    )
    assert research_session.status_code == 201

    execute = client.post(
        f"/api/v1/organizations/{organization_id}/research/sessions/"
        f"{research_session.json()['id']}/execute",
        headers=headers,
        json={"max_results_per_connector": 5},
    )
    assert execute.status_code == 200
    payload = execute.json()
    assert payload["session"]["status"] == "completed"
    assert payload["session"]["summary"]["source_count"] == 1
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["provider"] == "fixture"
    assert source["status"] == "ingested"
    assert source["knowledge_entry_id"] is not None
    assert len(source["content_sha256"]) == 64

    knowledge = client.get(
        f"/api/v1/organizations/{organization_id}/knowledge/search",
        headers=headers,
        params={"q": "payment reconciliation", "limit": 5},
    )
    assert knowledge.status_code == 200
    research_hits = [hit for hit in knowledge.json()["hits"] if hit["source"] == "knowledge"]
    assert research_hits
    assert research_hits[0]["source_uri"] == "fixture://payments/reconciliation"


def test_connector_config_rejects_secret_keys(client: TestClient) -> None:
    headers, organization_id = register_owner(client)
    response = client.post(
        f"/api/v1/organizations/{organization_id}/research/connectors",
        headers=headers,
        json={
            "name": "Unsafe Connector",
            "slug": "unsafe-connector",
            "provider": "fixture",
            "config": {"api_key": "should-never-be-stored"},
        },
    )
    assert response.status_code == 400
    assert "secrets" in response.json()["detail"].lower()


def test_manual_source_ingestion_is_deduplicated(client: TestClient) -> None:
    headers, organization_id = register_owner(client)
    research_session = client.post(
        f"/api/v1/organizations/{organization_id}/research/sessions",
        headers=headers,
        json={
            "title": "Manual evidence review",
            "query": "claims denial evidence",
        },
    )
    assert research_session.status_code == 201
    session_id = research_session.json()["id"]
    source_payload = {
        "title": "Claims denial evidence",
        "uri": "manual://healthcare/denials",
        "content": "Denial teams spend time classifying and reworking rejected claims.",
        "provider": "manual",
        "source_type": "analyst-note",
    }
    first = client.post(
        f"/api/v1/organizations/{organization_id}/research/sessions/{session_id}/sources",
        headers=headers,
        json=source_payload,
    )
    second = client.post(
        f"/api/v1/organizations/{organization_id}/research/sessions/{session_id}/sources",
        headers=headers,
        json=source_payload,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    sources = client.get(
        f"/api/v1/organizations/{organization_id}/research/sessions/{session_id}/sources",
        headers=headers,
    )
    assert sources.status_code == 200
    assert len(sources.json()) == 1
