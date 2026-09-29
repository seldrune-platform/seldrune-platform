from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

from backend.app.core.config import settings
from tests.test_autonomous_execution import client as _client  # noqa: F401
from tests.test_autonomous_execution import register_owner


def _connect_deepfacelive(client) -> str:
    register_owner(client)
    callback = "https://client.example/callback"
    registered = client.post(
        "/oauth/register",
        json={"client_name": "DeepFaceLive Setup Assistant", "redirect_uris": [callback]},
    )
    assert registered.status_code == 201
    client_id = registered.json()["client_id"]
    verifier = "z" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback,
        "state": "deepfacelive-bridge-state",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": "http://testserver/mcp",
        "scope": "seldrune.deepfacelive offline_access",
    }
    assert client.get("/oauth/authorize", params=params).status_code == 200
    csrf = client.cookies.get("seldrune_mcp_csrf")
    login = client.post(
        "/oauth/authorize/login",
        data={
            **params,
            "csrf_token": csrf,
            "email": "autonomy-founder@example.com",
            "password": "correct horse battery staple",
        },
        follow_redirects=False,
    )
    assert login.status_code == 303
    consent_page = client.get("/oauth/authorize", params=params)
    assert "DeepFaceLive companion access" in consent_page.text
    consent = client.post(
        "/oauth/authorize/consent",
        data={
            **params,
            "csrf_token": client.cookies.get("seldrune_mcp_csrf"),
            "decision": "allow",
        },
        follow_redirects=False,
    )
    assert consent.status_code == 303
    code = parse_qs(urlsplit(consent.headers["location"]).query)["code"][0]
    token = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": callback,
            "code": code,
            "code_verifier": verifier,
            "resource": "http://testserver/mcp",
        },
    )
    assert token.status_code == 200
    return token.json()["access_token"]


def _tool_call(
    client, access_token: str, request_id: int, name: str, arguments: dict | None = None
):
    return client.post(
        "/mcp/deepfacelive",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )


def _agent_post(client, path: str, token: str, body: dict):
    return client.post(path, headers={"Authorization": f"Bearer {token}"}, json=body)


def test_deepfacelive_endpoint_is_scoped_and_pairs_a_local_agent(
    _client, monkeypatch
) -> None:  # noqa: F811
    client = _client
    monkeypatch.setattr(settings, "public_app_url", "http://testserver")
    access_token = _connect_deepfacelive(client)
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    listing = client.post(
        "/mcp/deepfacelive",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert listing.status_code == 200
    names = {tool["name"] for tool in listing.json()["result"]["tools"]}
    assert names == {
        "pair_deepfacelive_agent",
        "deepfacelive_status",
        "deepfacelive_start",
        "deepfacelive_stop",
        "deepfacelive_command_status",
        "unpair_deepfacelive_agent",
    }
    assert "create_owner_command" not in names

    issued = _tool_call(client, access_token, 2, "pair_deepfacelive_agent")
    pairing = json.loads(issued.json()["result"]["content"][0]["text"])
    pairing_code = pairing["pairing_code"]
    assert len(pairing_code) >= 40

    pair_response = client.post(
        "/api/v1/deepfacelive/agent/pair",
        json={"pairing_code": pairing_code, "agent_name": "Test Windows companion"},
    )
    assert pair_response.status_code == 200
    agent_token = pair_response.json()["agent_token"]
    assert len(agent_token) >= 40
    assert client.post(
        "/api/v1/deepfacelive/agent/pair",
        json={"pairing_code": pairing_code},
    ).status_code == 400

    start = _tool_call(client, access_token, 3, "deepfacelive_start")
    command = json.loads(start.json()["result"]["content"][0]["text"])
    assert command["status"] == "pending"
    polled = _agent_post(
        client,
        "/api/v1/deepfacelive/agent/commands/next",
        agent_token,
        {"app_running": False, "app_pid": None, "agent_version": "test"},
    )
    assert polled.status_code == 200
    assert polled.json()["command"] == {"id": command["id"], "action": "start"}

    completed = _agent_post(
        client,
        f"/api/v1/deepfacelive/agent/commands/{command['id']}/result",
        agent_token,
        {
            "status": "completed",
            "app_running": True,
            "app_pid": 4242,
            "message": "DeepFaceLive is running on this computer.",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    status_response = _tool_call(client, access_token, 4, "deepfacelive_status")
    status_value = json.loads(status_response.json()["result"]["content"][0]["text"])
    assert status_value["paired"] is True
    assert status_value["online"] is True
    assert status_value["app_running"] is True

    bad_token = _agent_post(
        client,
        "/api/v1/deepfacelive/agent/commands/next",
        "invalid-token",
        {"app_running": False, "agent_version": "test"},
    )
    assert bad_token.status_code == 401
