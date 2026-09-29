from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


WEB = Path("backend/app/web")


def test_owner_console_serves_tools_workspace() -> None:
    with TestClient(app) as client:
        page = client.get("/console")
        assert page.status_code == 200
        assert 'id="tool-control"' in page.text
        assert "INTEGRATIONS &amp; CREATION TOOLS" in page.text
        assert "/console-assets/console-tools.css" in page.text
        assert "/console-assets/console-tools.js" in page.text


def test_tools_workspace_exposes_action_controls() -> None:
    html = (WEB / "index.html").read_text()
    script = (WEB / "console-tools.js").read_text()
    cosmic = (WEB / "console-cosmic-tabs.js").read_text()

    for element_id in (
        "tool-adapter-list",
        "secret-reference-form",
        "tool-definition-form",
        "tool-run-form",
        "tool-run-list",
        "tool-control-refresh",
        "tool-auto-activate",
        "tool-provider-preflight",
        "tool-provider-readiness",
        "tool-provider-preflight-results",
        "tool-clean-invalid",
    ):
        assert f'id="{element_id}"' in html

    assert "api('/tool-adapters')" in script
    assert "api('/secret-references')" in script
    assert "api('/tools')" in script
    assert "api('/tool-runs')" in script
    assert "api('/tool-bootstrap/status')" in script
    assert "api('/tool-defaults')" in script
    assert "api('/tool-bootstrap/preflight'" in script
    assert "/tool-bootstrap/credentials" in script
    connections = (WEB / "console-connections.js").read_text()
    assert 'id="integration-credential-form"' in connections
    assert 'id="integration-provider"' in connections
    assert 'id="integration-list"' in connections
    assert "/tool-bootstrap/credentials/verified" in connections
    assert 'option value="runpod">Runpod</option>' in connections
    assert "Runpod API key" in connections
    assert "runpod-api-key" in script
    assert "/tool-bootstrap/credentials/cleanup-invalid" in script
    assert "invalidCredentialCleanupAttempted" in script
    assert "cleanupInvalidCredentials({silent: true})" in script
    assert "data-provider-disconnect" in script
    assert "data-secret-remove" in script
    assert "verified and connected" in connections
    assert "api('/tool-bootstrap'" in script
    assert "Approve & execute" in script
    assert "credential reference" in script.lower()
    assert '["intelligence", "SYSTEM", "⚙"]' in cosmic
    assert 'move("#tool-control", "connections")' in cosmic
    assert "seldrune:workspace-change" in script
    assert "seldrune:console-ready', loadToolControl" not in script
