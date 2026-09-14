from fastapi.testclient import TestClient

from backend.app.main import app


def test_console_uses_account_login_without_manual_tokens() -> None:
    with TestClient(app) as client:
        page = client.get("/console").text
        assert 'id="email"' in page
        assert 'id="password"' in page
        assert 'id="bootstrap-form"' in page
        assert 'id="bootstrap-confirm"' in page
        assert "Organization ID" not in page
        assert "Access token" not in page


def test_console_script_resolves_bootstrap_and_owner_membership() -> None:
    with TestClient(app) as client:
        script = client.get("/console-assets/console.js").text
        assert "/auth/bootstrap-status" in script
        assert "/auth/register" in script
        assert "/auth/login" in script
        assert "/auth/me" in script
        assert "sessionStorage.removeItem" in script
        assert "role === 'owner'" in script
        assert "Passwords do not match." in script
