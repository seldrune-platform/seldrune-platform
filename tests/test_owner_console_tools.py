from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


WEB = Path("backend/app/web")


def test_owner_console_serves_tools_workspace() -> None:
    with TestClient(app) as client:
        page = client.get("/console")
        assert page.status_code == 200
        assert 'id="tool-control"' in page.text
        assert "GOVERNED ACTION FABRIC" in page.text
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
        "provider-vault-form",
        "provider-vault-provider",
        "provider-vault-secret",
        "provider-vault-status",
        "provider-vault-verified",
        "provider-vault-manual",
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
    assert "/tool-bootstrap/credentials/verified" in script
    assert "/tool-bootstrap/credentials/cleanup-invalid" in script
    assert "data-provider-disconnect" in script
    assert "data-secret-remove" in script
    assert "credential saved and activated" in script
    assert "api('/tool-bootstrap'" in script
    assert "Approve & execute" in script
    assert "credential reference" in script.lower()
    assert '["tools", "Tools", "⌁"]' in cosmic
    assert 'move("#tool-control", "tools")' in cosmic
