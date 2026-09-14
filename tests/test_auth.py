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


def registration_payload() -> dict[str, str]:
    return {
        "email": "founder@example.com",
        "password": "correct horse battery staple",
        "display_name": "Founder",
        "organization_name": "Seldrune",
        "organization_slug": "seldrune",
    }


def test_register_login_and_protected_routes(client: TestClient) -> None:
    status_before = client.get("/api/v1/auth/bootstrap-status")
    assert status_before.status_code == 200
    assert status_before.json() == {"required": True}

    register = client.post("/api/v1/auth/register", json=registration_payload())
    assert register.status_code == 201
    registration = register.json()
    assert registration["token_type"] == "bearer"

    status_after = client.get("/api/v1/auth/bootstrap-status")
    assert status_after.status_code == 200
    assert status_after.json() == {"required": False}

    token = registration["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    profile = me.json()
    assert profile["user"]["email"] == "founder@example.com"
    assert profile["memberships"][0]["role"] == "owner"
    assert "members:read" in profile["memberships"][0]["permissions"]

    organization_id = profile["memberships"][0]["organization"]["id"]
    members = client.get(
        f"/api/v1/organizations/{organization_id}/members",
        headers=headers,
    )
    assert members.status_code == 200
    assert len(members.json()) == 1

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "founder@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_unauthenticated_me_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_registration_is_locked_after_first_owner(client: TestClient) -> None:
    first = client.post("/api/v1/auth/register", json=registration_payload())
    assert first.status_code == 201

    second_payload = {
        **registration_payload(),
        "email": "attacker@example.com",
        "organization_name": "Other",
        "organization_slug": "other",
    }
    second = client.post("/api/v1/auth/register", json=second_payload)
    assert second.status_code == 403
    assert second.json()["detail"] == "Owner onboarding is already complete"


def test_wrong_password_is_rejected(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=registration_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "founder@example.com", "password": "definitely-wrong"},
    )
    assert response.status_code == 401
