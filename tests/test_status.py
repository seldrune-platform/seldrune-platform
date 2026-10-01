from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.routes import status as status_route
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.main import app

client = TestClient(app)


@contextmanager
def _client_with_schema(
    revision: str | None,
    *,
    create_version_table: bool = True,
) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if create_version_table:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL)")
            )
            if revision is not None:
                connection.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                    {"revision": revision},
                )

    session_local = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_status_endpoint() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["ready"] is True
    assert body["service"] == "seldrune-platform"
    assert body["version"] == settings.app_version
    assert body["environment"] == "development"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["schema"]["required"] is False
    assert body["checks"]["schema"]["expected_revision"]
    assert body["checks"]["model_provider"] == {
        "status": "ok",
        "provider": "mock",
        "model": "mock-v1",
        "live_ai": False,
    }
    assert set(body["release"]) == {"sha", "source"}
    assert body["checked_at"]


def test_ready_is_strict_for_current_production_schema(monkeypatch) -> None:
    expected_revision = status_route._expected_schema_revision()
    assert expected_revision is not None
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "model_provider", "mock")

    with _client_with_schema(expected_revision) as test_client:
        response = test_client.get("/api/v1/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["checks"]["schema"] == {
        "status": "ok",
        "schema_current": True,
        "current_revision": expected_revision,
        "expected_revision": expected_revision,
        "required": True,
    }


def test_schema_mismatch_degrades_status_and_returns_503(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "model_provider", "mock")

    with _client_with_schema("0014_agent_tool_grants") as test_client:
        status_response = test_client.get("/api/v1/status")
        ready_response = test_client.get("/api/v1/ready")

    assert status_response.status_code == 200
    assert status_response.json()["ready"] is False
    assert status_response.json()["checks"]["schema"]["status"] == "mismatch"
    assert ready_response.status_code == 503
    assert ready_response.json()["ready"] is False


def test_missing_schema_metadata_returns_503_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "model_provider", "mock")

    with _client_with_schema(None, create_version_table=False) as test_client:
        response = test_client.get("/api/v1/ready")

    assert response.status_code == 503
    schema = response.json()["checks"]["schema"]
    assert schema["status"] == "unavailable"
    assert schema["schema_current"] is False
    assert schema["current_revision"] is None
    assert schema["current_error"]


def test_unconfigured_model_provider_returns_503(monkeypatch) -> None:
    expected_revision = status_route._expected_schema_revision()
    assert expected_revision is not None
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "model_provider", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with _client_with_schema(expected_revision) as test_client:
        response = test_client.get("/api/v1/ready")

    assert response.status_code == 503
    provider = response.json()["checks"]["model_provider"]
    assert provider["status"] == "unconfigured"
    assert provider["live_ai"] is False


def test_explicit_release_sha_precedes_platform_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(settings, "release_sha", "explicit-release-sha")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-sha")
    monkeypatch.setenv("GITHUB_SHA", "github-sha")

    response = client.get("/api/v1/status")

    assert response.status_code == 200
    assert response.json()["release"] == {
        "sha": "explicit-release-sha",
        "source": "seldrune",
    }



def test_compatible_model_provider_is_ready_with_configured_endpoint(
    monkeypatch,
) -> None:
    expected_revision = status_route._expected_schema_revision()
    assert expected_revision is not None
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "model_provider", "openai_compatible")
    monkeypatch.setattr(
        settings,
        "model_compatible_base_url",
        "http://localhost:11434/v1",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with _client_with_schema(expected_revision) as test_client:
        response = test_client.get("/api/v1/ready")

    assert response.status_code == 200
    provider = response.json()["checks"]["model_provider"]
    assert provider == {
        "status": "ok",
        "provider": "openai_compatible",
        "model": settings.model_default,
        "live_ai": True,
    }


def test_temporary_astra_bridge_is_hidden_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("SELDRUNE_ASTRA_BRIDGE_ENABLED", raising=False)
    monkeypatch.delenv("SELDRUNE_ASTRA_BRIDGE_TOKEN", raising=False)
    response = client.get("/api/v1/internal/astra-runpod-review", params={"token": "nope"})
    assert response.status_code == 404


def test_temporary_astra_bridge_rejects_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("SELDRUNE_ASTRA_BRIDGE_ENABLED", "1")
    monkeypatch.setenv("SELDRUNE_ASTRA_BRIDGE_TOKEN", "expected-token")
    response = client.get("/api/v1/internal/astra-runpod-review", params={"token": "wrong-token"})
    assert response.status_code == 404
