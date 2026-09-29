from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from backend.app.core.config import settings
from tests.test_autonomous_execution import client as _client
from tests.test_autonomous_execution import register_owner


def _connect_owner(client) -> tuple[str, str, str]:
    _token, organization_id = register_owner(client)
    callback = "https://client.example/callback"
    registered = client.post(
        "/oauth/register",
        json={
            "client_name": "Seldrune bridge test",
            "redirect_uris": [callback],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert registered.status_code == 201
    client_id = registered.json()["client_id"]

    verifier = "a" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback,
        "state": "test-state-123",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": "http://testserver/mcp",
        "scope": "seldrune.owner offline_access",
    }

    login_page = client.get("/oauth/authorize", params=params)
    assert login_page.status_code == 200
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
    assert consent_page.status_code == 200
    assert "Review Seldrune access" in consent_page.text
    csrf = client.cookies.get("seldrune_mcp_csrf")
    consent = client.post(
        "/oauth/authorize/consent",
        data={**params, "csrf_token": csrf, "decision": "allow"},
        follow_redirects=False,
    )
    assert consent.status_code == 303
    code = parse_qs(urlsplit(consent.headers["location"]).query)["code"][0]

    token_response = client.post(
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
    assert token_response.status_code == 200
    return token_response.json()["access_token"], organization_id, client_id


def _mcp_call(client, access_token: str, request_id: int, tool_name: str, arguments: dict):
    return client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    )


def test_oauth_pkce_and_owner_actions_keep_approval_separate(
    _client, monkeypatch
) -> None:  # noqa: F811
    client = _client
    monkeypatch.setattr(settings, "public_app_url", "http://testserver")
    access_token, organization_id, _client_id = _connect_owner(client)

    listed = client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
    )
    assert listed.status_code == 200
    tool_names = {tool["name"] for tool in listed.json()["result"]["tools"]}
    assert {"create_owner_command", "approve_owner_command", "execute_owner_command"} <= tool_names

    created = _mcp_call(
        client,
        access_token,
        2,
        "create_owner_command",
        {
            "organization_id": organization_id,
            "objective": "Review the organization's current operating priorities",
        },
    )
    assert created.status_code == 200
    command = json.loads(created.json()["result"]["content"][0]["text"])
    command_id = command["id"]
    assert command["context"]["owner_command"]["approval_status"] == "awaiting_approval"

    execution = _mcp_call(
        client,
        access_token,
        3,
        "execute_owner_command",
        {"organization_id": organization_id, "command_id": command_id},
    )
    assert execution.json()["result"]["isError"] is True
    assert "requires approval" in execution.json()["result"]["content"][0]["text"]

    approved = _mcp_call(
        client,
        access_token,
        4,
        "approve_owner_command",
        {"organization_id": organization_id, "command_id": command_id},
    )
    approved_command = json.loads(approved.json()["result"]["content"][0]["text"])
    assert approved_command["context"]["owner_command"]["approval_status"] == "approved"

    denied_org = _mcp_call(
        client,
        access_token,
        5,
        "get_owner_dashboard",
        {"organization_id": str(uuid4())},
    )
    assert denied_org.json()["result"]["isError"] is True
    assert "Owner role required" in denied_org.json()["result"]["content"][0]["text"]


def test_oauth_code_is_pkce_bound_single_use_and_refresh_replay_revokes_family(
    _client, monkeypatch
) -> None:  # noqa: F811
    client = _client
    monkeypatch.setattr(settings, "public_app_url", "http://testserver")
    register_owner(client)
    callback = "https://client.example/callback"
    registered = client.post(
        "/oauth/register",
        json={"client_name": "PKCE test", "redirect_uris": [callback]},
    )
    client_id = registered.json()["client_id"]
    verifier = "b" * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback,
        "state": "state-456",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": "http://testserver/mcp",
        "scope": "seldrune.owner offline_access",
    }
    client.get("/oauth/authorize", params=params)
    csrf = client.cookies.get("seldrune_mcp_csrf")
    client.post(
        "/oauth/authorize/login",
        data={
            **params,
            "csrf_token": csrf,
            "email": "autonomy-founder@example.com",
            "password": "correct horse battery staple",
        },
        follow_redirects=False,
    )
    client.get("/oauth/authorize", params=params)
    csrf = client.cookies.get("seldrune_mcp_csrf")
    consent = client.post(
        "/oauth/authorize/consent",
        data={**params, "csrf_token": csrf, "decision": "allow"},
        follow_redirects=False,
    )
    code = parse_qs(urlsplit(consent.headers["location"]).query)["code"][0]
    body = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": callback,
        "code": code,
        "resource": "http://testserver/mcp",
    }
    wrong_verifier = client.post(
        "/oauth/token",
        data={**body, "code_verifier": "c" * 43},
    )
    assert wrong_verifier.json()["error"] == "invalid_grant"

    token_response = client.post(
        "/oauth/token",
        data={**body, "code_verifier": verifier},
    )
    assert token_response.status_code == 200
    replay = client.post(
        "/oauth/token",
        data={**body, "code_verifier": verifier},
    )
    assert replay.json()["error"] == "invalid_grant"

    refresh = token_response.json()["refresh_token"]
    rotated = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh,
        },
    )
    assert rotated.status_code == 200
    reuse = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh,
        },
    )
    assert reuse.json()["error"] == "invalid_grant"
    revoked_family = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": rotated.json()["refresh_token"],
        },
    )
    assert revoked_family.json()["error"] == "invalid_grant"
