import base64
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
