from fastapi.testclient import TestClient

from backend.app.main import app


def test_command_monitor_assets_are_served() -> None:
    with TestClient(app) as client:
        page = client.get("/console-assets/command-monitor.html")
        assert page.status_code == 200
        assert "Seldrune Command Monitor" in page.text
        assert "/console-assets/command-monitor.js" in page.text

        script = client.get("/console-assets/command-monitor.js")
        assert script.status_code == 200
        assert "Routing confidence" in script.text
        assert "model-invocations" in script.text
        assert "owner-commands" in script.text
