from __future__ import annotations

import json

import pytest

from backend.app.services import external_actions, unreal_worker_client
from backend.app.services.tool_gateway import ToolGatewayError


def _credential(url: str = "https://worker.example.com") -> str:
    return json.dumps({"base_url": url, "token": "test-worker-token"})


def test_unreal_worker_client_uses_bearer_token_and_fixed_health_route(monkeypatch) -> None:
    observed = {}
    monkeypatch.setattr(unreal_worker_client, "_assert_public_host", lambda host, port: None)

    class Response:
        status_code = 200

        def json(self):
            return {"service": "seldrune-unreal-worker", "status": "ready"}

    def fake_request(method, url, **kwargs):
        observed.update(method=method, url=url, **kwargs)
        return Response()

    monkeypatch.setattr(unreal_worker_client.httpx, "request", fake_request)
    result = unreal_worker_client.request_unreal_worker(
        _credential(),
        method="GET",
        path="/v1/healthz",
    )
    assert result["status"] == "ready"
    assert observed["url"] == "https://worker.example.com/v1/healthz"
    assert observed["headers"]["Authorization"] == "Bearer test-worker-token"
    assert observed["follow_redirects"] is False


def test_unreal_worker_connection_rejects_non_https_and_local_hosts() -> None:
    with pytest.raises(ToolGatewayError, match="HTTPS"):
        unreal_worker_client.parse_unreal_worker_credential(
            _credential("http://worker.example.com")
        )
    with pytest.raises(ToolGatewayError, match="publicly reachable"):
        unreal_worker_client.parse_unreal_worker_credential(
            _credential("https://localhost")
        )


def test_unreal_install_action_only_queues_a_validated_version(monkeypatch) -> None:
    observed = {}

    def fake_request(credential, *, method, path, json_body=None):
        observed.update(method=method, path=path, json_body=json_body)
        return {"job_id": "job-123", "status": "queued", "version": "5.4"}

    monkeypatch.setattr(external_actions, "request_unreal_worker", fake_request)
    result = external_actions.unreal_install_engine(
        {"version": "5.4"},
        _credential(),
    )
    assert observed == {
        "method": "POST",
        "path": "/v1/engine/install",
        "json_body": {"version": "5.4"},
    }
    assert result["job_id"] == "job-123"
    assert result["status"] == "queued"
    assert "test-worker-token" not in str(result)

    with pytest.raises(ToolGatewayError, match="Engine version"):
        external_actions.unreal_install_engine(
            {"version": "https://attacker.example/file"},
            _credential(),
        )


def test_unreal_tools_have_owner_approved_install_action() -> None:
    entries = {
        item["action_name"]: item
        for item in external_actions.default_external_action_catalog()
        if item["provider"] == "unreal"
    }
    assert set(entries) == {"engine-status", "install-engine"}
    assert entries["engine-status"]["risk_level"] == "low"
    assert entries["install-engine"]["risk_level"] == "high"
