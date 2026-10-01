import base64
import hashlib
import hmac
import json
from email import policy
from email.parser import BytesParser

import httpx
import pytest

from backend.app.services import external_actions
from backend.app.services.tool_gateway import ToolGatewayError


def _response(
    status_code: int,
    *,
    json_data: dict | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", "https://provider.example.test/action")
    if json_data is None:
        return httpx.Response(
            status_code,
            headers=headers,
            request=request,
        )
    return httpx.Response(
        status_code,
        json=json_data,
        headers=headers,
        request=request,
    )


def test_gmail_send_message_builds_rfc822_and_receipt(monkeypatch) -> None:
    observed = {}

    def fake_post(url, *, headers, json, timeout):
        observed.update(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return _response(
            200,
            json_data={"id": "msg-123", "threadId": "thread-5"},
        )

    monkeypatch.setattr(external_actions.httpx, "post", fake_post)
    output = external_actions.gmail_send_message(
        {
            "to": "owner@example.com",
            "subject": "Seldrune receipt",
            "body": "Deployment complete.",
        },
        "gmail-token",
    )

    assert observed["url"].endswith("/gmail/v1/users/me/messages/send")
    assert observed["headers"]["Authorization"] == "Bearer gmail-token"
    encoded = observed["json"]["raw"]
    decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
    message = BytesParser(policy=policy.default).parsebytes(decoded)
    assert message["To"] == "owner@example.com"
    assert message["Subject"] == "Seldrune receipt"
    assert "Deployment complete." in message.get_body().get_content()
    assert output["evidence"]["receipt_id"] == "gmail:msg-123"


def test_github_create_issue_returns_provider_receipt(monkeypatch) -> None:
    observed = {}

    def fake_post(url, *, headers, json, timeout):
        observed.update({"url": url, "headers": headers, "json": json})
        return _response(
            201,
            json_data={
                "id": 991,
                "number": 7,
                "html_url": "https://github.com/acme/app/issues/7",
            },
        )

    monkeypatch.setattr(external_actions.httpx, "post", fake_post)
    output = external_actions.github_create_issue(
        {
            "owner": "acme",
            "repo": "app",
            "title": "Investigate failure",
            "body": "Evidence attached.",
        },
        "github-token",
    )

    assert observed["url"].endswith("/repos/acme/app/issues")
    assert observed["headers"]["Authorization"] == "Bearer github-token"
    assert observed["json"]["title"] == "Investigate failure"
    assert output["evidence"]["receipt_id"] == "github-issue:991"


def test_github_comment_returns_provider_receipt(monkeypatch) -> None:
    def fake_post(url, *, headers, json, timeout):
        assert url.endswith("/repos/acme/app/issues/12/comments")
        assert json == {"body": "CI is green."}
        return _response(
            201,
            json_data={
                "id": 3001,
                "html_url": "https://github.com/acme/app/pull/12#issuecomment-3001",
            },
        )

    monkeypatch.setattr(external_actions.httpx, "post", fake_post)
    output = external_actions.github_comment(
        {
            "owner": "acme",
            "repo": "app",
            "number": 12,
            "body": "CI is green.",
        },
        "github-token",
    )
    assert output["evidence"]["receipt_id"] == "github-comment:3001"


def test_github_create_pull_request_returns_provider_receipt(monkeypatch) -> None:
    observed = {}

    def fake_post(url, *, headers, json, timeout):
        observed.update({"url": url, "headers": headers, "json": json})
        return _response(
            201,
            json_data={
                "id": 7001,
                "number": 41,
                "state": "open",
                "html_url": "https://github.com/acme/app/pull/41",
            },
        )

    monkeypatch.setattr(external_actions.httpx, "post", fake_post)
    output = external_actions.github_create_pull_request(
        {
            "owner": "acme",
            "repo": "app",
            "title": "Ship governed tools",
            "head": "feature/tools",
            "base": "main",
            "body": "Adds provider actions.",
            "draft": True,
        },
        "github-token",
    )

    assert observed["url"].endswith("/repos/acme/app/pulls")
    assert observed["json"]["head"] == "feature/tools"
    assert observed["json"]["base"] == "main"
    assert observed["json"]["draft"] is True
    assert output["number"] == 41
    assert output["evidence"]["receipt_id"] == "github-pull:7001"


def test_github_merge_pull_request_returns_merge_receipt(monkeypatch) -> None:
    observed = {}

    def fake_put(url, *, headers, json, timeout):
        observed.update({"url": url, "headers": headers, "json": json})
        return _response(
            200,
            json_data={
                "sha": "abc123",
                "merged": True,
                "message": "Pull Request successfully merged",
            },
        )

    monkeypatch.setattr(external_actions.httpx, "put", fake_put)
    output = external_actions.github_merge_pull_request(
        {
            "owner": "acme",
            "repo": "app",
            "pull_number": 41,
            "merge_method": "squash",
            "sha": "head123",
        },
        "github-token",
    )

    assert observed["url"].endswith("/repos/acme/app/pulls/41/merge")
    assert observed["json"] == {
        "merge_method": "squash",
        "sha": "head123",
    }
    assert output["merged"] is True
    assert output["evidence"]["receipt_id"] == "github-merge:abc123"


def test_github_merge_pull_request_fails_when_provider_does_not_merge(
    monkeypatch,
) -> None:
    def fake_put(url, *, headers, json, timeout):
        return _response(
            200,
            json_data={
                "sha": None,
                "merged": False,
                "message": "Branch protection blocked merge",
            },
        )

    monkeypatch.setattr(external_actions.httpx, "put", fake_put)
    with pytest.raises(ToolGatewayError, match="Branch protection blocked merge"):
        external_actions.github_merge_pull_request(
            {
                "owner": "acme",
                "repo": "app",
                "pull_number": 41,
            },
            "github-token",
        )


def test_github_dispatch_uses_workflow_run_receipt(monkeypatch) -> None:
    def fake_post(url, *, headers, json, timeout):
        assert url.endswith("/actions/workflows/deploy.yml/dispatches")
        assert json == {"ref": "main", "inputs": {"environment": "production"}}
        return _response(
            200,
            json_data={
                "workflow_run_id": 555,
                "html_url": "https://github.com/acme/app/actions/runs/555",
            },
        )

    monkeypatch.setattr(external_actions.httpx, "post", fake_post)
    monkeypatch.setattr(
        external_actions,
        "_workflow_dispatch_runs",
        lambda **_: [],
    )
    output = external_actions.github_dispatch_workflow(
        {
            "owner": "acme",
            "repo": "app",
            "workflow_id": "deploy.yml",
            "ref": "main",
            "inputs": {"environment": "production"},
        },
        "github-token",
    )
    assert output["evidence"]["receipt_id"] == "github-workflow:555"


def test_github_dispatch_accepts_request_id_for_legacy_empty_response(monkeypatch) -> None:
    def fake_post(url, *, headers, json, timeout):
        return _response(
            204,
            headers={"x-github-request-id": "REQ-ABC"},
        )

    monkeypatch.setattr(external_actions.httpx, "post", fake_post)
    monkeypatch.setattr(
        external_actions,
        "_workflow_dispatch_runs",
        lambda **_: [],
    )
    monkeypatch.setattr(
        external_actions,
        "_discover_dispatched_workflow_run",
        lambda **_: None,
    )
    output = external_actions.github_dispatch_workflow(
        {
            "owner": "acme",
            "repo": "app",
            "workflow_id": "deploy.yml",
            "ref": "main",
        },
        "github-token",
    )
    assert output["evidence"]["receipt_id"] == "github-workflow:REQ-ABC"


def test_render_deploy_service_returns_deploy_receipt(monkeypatch) -> None:
    observed = {}

    def fake_post(url, *, headers, json, timeout):
        observed.update({"url": url, "headers": headers, "json": json})
        return _response(
            201,
            json_data={
                "id": "dep-cxyz",
                "status": "build_in_progress",
                "commit": {"id": "abc123"},
            },
        )

    monkeypatch.setattr(external_actions.httpx, "post", fake_post)
    output = external_actions.render_deploy_service(
        {
            "service_id": "srv-c123",
            "commit_id": "abc123",
            "clear_cache": True,
        },
        "render-token",
    )

    assert observed["url"].endswith("/v1/services/srv-c123/deploys")
    assert observed["headers"]["Authorization"] == "Bearer render-token"
    assert observed["json"] == {
        "commitId": "abc123",
        "clearCache": "clear",
    }
    assert output["evidence"]["receipt_id"] == "render-deploy:dep-cxyz"


def test_external_adapter_requires_credential() -> None:
    with pytest.raises(ToolGatewayError, match="credential is required"):
        external_actions.gmail_send_message(
            {"to": "a@example.com", "subject": "Hi", "body": "Hello"},
            None,
        )

def _portable_ci_receipt(release_sha: str = "abc123") -> dict:
    return {
        "version": "seldrune-ci-v1",
        "status": "success",
        "release_sha": release_sha,
        "checks": [
            "postgres-ready",
            "ruff",
            "pytest",
            "alembic-upgrade-head",
            "production-ready",
        ],
        "ready": {
            "ready": True,
            "status": "ready",
            "environment": "production",
            "release": {
                "sha": release_sha,
                "source": "seldrune",
            },
        },
    }


def _portable_ci_signature(receipt: dict, key: str) -> str:
    canonical = json.dumps(
        receipt,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hmac.new(
        key.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def test_portable_ci_signed_receipt_verifies_exact_release() -> None:
    key = "portable-ci-test-signing-key"
    receipt = _portable_ci_receipt("deadbeef")
    output = external_actions.portable_ci_verify_receipt(
        {
            "receipt": receipt,
            "signature": _portable_ci_signature(receipt, key),
        },
        key,
    )

    assert output["verified"] is True
    assert output["conclusion"] == "success"
    assert output["release_sha"] == "deadbeef"
    assert output["head_sha"] == "deadbeef"
    assert output["signature_verified"] is True
    assert output["evidence"]["provider"] == "portable-ci"
    assert output["evidence"]["receipt_id"].startswith(
        "portable-ci:deadbeef:"
    )


def test_portable_ci_receipt_rejects_tampering() -> None:
    key = "portable-ci-test-signing-key"
    receipt = _portable_ci_receipt("deadbeef")
    signature = _portable_ci_signature(receipt, key)
    receipt["release_sha"] = "forged"

    with pytest.raises(ToolGatewayError, match="signature mismatch"):
        external_actions.portable_ci_verify_receipt(
            {
                "receipt": receipt,
                "signature": signature,
            },
            key,
        )


def test_portable_ci_receipt_requires_all_evidence_checks() -> None:
    key = "portable-ci-test-signing-key"
    receipt = _portable_ci_receipt("deadbeef")
    receipt["checks"].remove("pytest")

    with pytest.raises(ToolGatewayError, match="missing required checks: pytest"):
        external_actions.portable_ci_verify_receipt(
            {
                "receipt": receipt,
                "signature": _portable_ci_signature(receipt, key),
            },
            key,
        )


def test_portable_ci_catalog_uses_secret_backed_credential() -> None:
    entry = next(
        item
        for item in external_actions.default_external_action_catalog()
        if item["provider"] == "portable-ci"
        and item["action_name"] == "verify-receipt"
    )
    assert entry["risk_level"] == "low"
    assert entry["credential_env_locator"] == "SELDRUNE_CI_RECEIPT_HMAC_KEY"
    assert entry["input_schema"]["required"] == ["receipt", "signature"]




def test_github_app_private_key_mints_installation_token(monkeypatch) -> None:
    external_actions._GITHUB_APP_TOKEN_CACHE.clear()
    monkeypatch.setenv("SELDRUNE_GITHUB_APP_ID", "12345")
    monkeypatch.setenv("SELDRUNE_GITHUB_APP_INSTALLATION_ID", "777")
    observed = {"jwt_payload": None, "requests": []}

    def fake_encode(payload, private_key, algorithm):
        observed["jwt_payload"] = payload
        assert "BEGIN PRIVATE KEY" in private_key
        assert algorithm == "RS256"
        return "signed-app-jwt"

    def fake_post(url, *, headers, json, timeout):
        observed["requests"].append(
            {"url": url, "headers": headers, "json": json}
        )
        if url.endswith("/app/installations/777/access_tokens"):
            assert headers["Authorization"] == "Bearer signed-app-jwt"
            return _response(
                201,
                json_data={
                    "token": "installation-token",
                    "expires_at": "2099-01-01T00:00:00Z",
                },
            )
        assert url.endswith("/repos/acme/app/issues")
        assert headers["Authorization"] == "Bearer installation-token"
        return _response(
            201,
            json_data={
                "id": 992,
                "number": 8,
                "html_url": "https://github.com/acme/app/issues/8",
            },
        )

    monkeypatch.setattr(external_actions.jwt, "encode", fake_encode)
    monkeypatch.setattr(external_actions.httpx, "post", fake_post)

    output = external_actions.github_create_issue(
        {
            "owner": "acme",
            "repo": "app",
            "title": "App auth test",
        },
        "-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----",
    )

    assert output["evidence"]["receipt_id"] == "github-issue:992"
    assert observed["jwt_payload"]["iss"] == "12345"
    assert len(observed["requests"]) == 2


def test_github_app_private_key_requires_installation_metadata(
    monkeypatch,
) -> None:
    external_actions._GITHUB_APP_TOKEN_CACHE.clear()
    monkeypatch.setenv("SELDRUNE_GITHUB_APP_ID", "12345")
    monkeypatch.delenv("SELDRUNE_GITHUB_APP_INSTALLATION_ID", raising=False)

    with pytest.raises(
        ToolGatewayError,
        match="App id and installation id are required",
    ):
        external_actions.github_create_issue(
            {
                "owner": "acme",
                "repo": "app",
                "title": "Missing installation",
            },
            "-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----",
        )


def test_runpod_list_pods_sanitizes_environment_and_ssh_fields(monkeypatch) -> None:
    observed = {}

    def fake_get(url, *, headers, params, timeout):
        observed.update(url=url, authorization=headers.get("Authorization"), params=params)
        return _response(
            200,
            json_data={
                "pods": [
                    {
                        "id": "pod-123",
                        "name": "deepface-test",
                        "status": "RUNNING",
                        "image": "runpod/pytorch:test",
                        "env": {"RUNPOD_PRIVATE": "hidden-secret"},
                        "ssh": {"direct": {"command": "ssh user@host"}},
                        "gpu": {
                            "id": "NVIDIA GeForce RTX 4090",
                            "count": 1,
                            "memory": 24,
                            "vcpuCount": 8,
                            "privateKey": "hidden-private-key",
                        },
                        "cost": 0.44,
                    }
                ],
                "pagination": {"nextCursor": "next-page", "hasNextPage": True},
            },
        )

    monkeypatch.setattr(external_actions.httpx, "get", fake_get)
    output = external_actions.runpod_list_pods({"limit": 10}, "runpod-secret-token")

    assert observed == {
        "url": "https://api.runpod.io/v2/pods",
        "authorization": "Bearer runpod-secret-token",
        "params": {"limit": 10},
    }
    assert output["pods"] == [
        {
            "id": "pod-123",
            "name": "deepface-test",
            "image": "runpod/pytorch:test",
            "status": "RUNNING",
            "cost": 0.44,
            "gpu": {
                "id": "NVIDIA GeForce RTX 4090",
                "count": 1,
                "memory": 24,
                "vcpuCount": 8,
            },
        }
    ]
    assert output["pagination"] == {"next_cursor": "next-page", "has_next_page": True}
    assert "hidden-secret" not in str(output)
    assert "hidden-private-key" not in str(output)
    assert "ssh user@host" not in str(output)
    assert "runpod-secret-token" not in str(output)


def test_runpod_get_and_lifecycle_use_v2_routes(monkeypatch) -> None:
    observed = {"gets": [], "posts": []}

    def fake_get(url, *, headers, timeout, params=None):
        observed["gets"].append((url, headers.get("Authorization")))
        return _response(
            200,
            json_data={
                "id": "pod/with space",
                "status": "EXITED",
                "env": {"SECRET": "hide-me"},
                "ssh": {"direct": {"command": "ssh user@host"}},
            },
        )

    def fake_post(url, *, headers, json, timeout):
        observed["posts"].append((url, headers.get("Authorization"), json))
        status = "STARTING" if json["action"] == "start" else "EXITED"
        return _response(
            200,
            json_data={
                "id": "pod/with space",
                "status": status,
                "env": {"SECRET": "hide-me"},
                "ssh": {"direct": {"command": "ssh user@host"}},
            },
        )

    monkeypatch.setattr(external_actions.httpx, "get", fake_get)
    monkeypatch.setattr(external_actions.httpx, "post", fake_post)

    details = external_actions.runpod_get_pod(
        {"pod_id": "pod/with space"}, "runpod-secret-token"
    )
    started = external_actions.runpod_start_pod(
        {"pod_id": "pod/with space"}, "runpod-secret-token"
    )
    stopped = external_actions.runpod_stop_pod(
        {"pod_id": "pod/with space"}, "runpod-secret-token"
    )

    encoded_path = "pod%2Fwith%20space"
    assert observed["gets"] == [
        (f"https://api.runpod.io/v2/pods/{encoded_path}", "Bearer runpod-secret-token")
    ]
    assert observed["posts"] == [
        (
            f"https://api.runpod.io/v2/pods/{encoded_path}/action",
            "Bearer runpod-secret-token",
            {"action": "start"},
        ),
        (
            f"https://api.runpod.io/v2/pods/{encoded_path}/action",
            "Bearer runpod-secret-token",
            {"action": "stop"},
        ),
    ]
    assert details["pod"] == {"id": "pod/with space", "status": "EXITED"}
    assert started["action"] == "start"
    assert started["accepted"] is True
    assert started["observed_status"] == "STARTING"
    assert stopped["action"] == "stop"
    assert stopped["observed_status"] == "EXITED"
    assert "hide-me" not in str([details, started, stopped])
    assert "ssh user@host" not in str([details, started, stopped])


def test_runpod_catalog_requires_owner_approval_for_lifecycle_actions() -> None:
    entries = {
        item["action_name"]: item
        for item in external_actions.default_external_action_catalog()
        if item["provider"] == "runpod"
    }

    assert set(entries) == {"list-pods", "get-pod", "start-pod", "stop-pod"}
    assert all(
        item["credential_slug"] == "runpod-api-key"
        and item["credential_env_locator"] == "SELDRUNE_RUNPOD_API_KEY"
        for item in entries.values()
    )
    assert entries["list-pods"]["risk_level"] == "low"
    assert entries["get-pod"]["risk_level"] == "low"
    assert entries["start-pod"]["risk_level"] == "high"
    assert entries["stop-pod"]["risk_level"] == "high"
