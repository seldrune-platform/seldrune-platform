from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

import httpx

from backend.app.services.tool_gateway import ToolGatewayError, register_external_action


_REQUEST_TIMEOUT_SECONDS = 20.0
_GITHUB_API_VERSION = "2026-03-10"


def _credential(value: str | None, provider: str) -> str:
    if not value:
        raise ToolGatewayError(f"{provider} credential is required")
    return value


def _text(payload: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = payload.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ToolGatewayError(f"{key} must be a non-empty string")
    return value.strip()


def _integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        raise ToolGatewayError(f"{key} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolGatewayError(f"{key} must be an integer") from exc
    if parsed < 1:
        raise ToolGatewayError(f"{key} must be positive")
    return parsed


def _json_response(response: httpx.Response, provider: str) -> dict[str, Any]:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolGatewayError(
            f"{provider} request failed with HTTP {response.status_code}"
        ) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise ToolGatewayError(f"{provider} returned a non-JSON response") from exc
    if not isinstance(data, dict):
        raise ToolGatewayError(f"{provider} returned an invalid response")
    return data


def gmail_send_message(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "Gmail")
    recipient = _text(payload, "to")
    subject = _text(payload, "subject")
    body = _text(payload, "body")

    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    sender = payload.get("from")
    if isinstance(sender, str) and sender.strip():
        message["From"] = sender.strip()
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    response = httpx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw": raw},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "Gmail")
    message_id = data.get("id")
    if not message_id:
        raise ToolGatewayError("Gmail response did not include a message id")
    return {
        "message_id": str(message_id),
        "thread_id": data.get("threadId"),
        "label_ids": data.get("labelIds") or [],
        "evidence": {
            "receipt_id": f"gmail:{message_id}",
            "provider": "gmail",
        },
    }


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        "User-Agent": "Seldrune-STI",
    }


def github_create_issue(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    title = _text(payload, "title")
    body = _text(payload, "body", required=False)
    request_body: dict[str, Any] = {"title": title}
    if body:
        request_body["body"] = body

    response = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        headers=_github_headers(token),
        json=request_body,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    issue_id = data.get("id")
    if not issue_id:
        raise ToolGatewayError("GitHub response did not include an issue id")
    return {
        "issue_id": issue_id,
        "number": data.get("number"),
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": f"github-issue:{issue_id}",
            "provider": "github",
        },
    }


def github_comment(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    number = _integer(payload, "number")
    body = _text(payload, "body")

    response = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments",
        headers=_github_headers(token),
        json={"body": body},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    comment_id = data.get("id")
    if not comment_id:
        raise ToolGatewayError("GitHub response did not include a comment id")
    return {
        "comment_id": comment_id,
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": f"github-comment:{comment_id}",
            "provider": "github",
        },
    }


def github_dispatch_workflow(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    workflow = quote(_text(payload, "workflow_id"), safe="")
    ref = _text(payload, "ref")
    inputs = payload.get("inputs") or {}
    if not isinstance(inputs, dict):
        raise ToolGatewayError("inputs must be an object")

    response = httpx.post(
        (
            f"https://api.github.com/repos/{owner}/{repo}/actions/"
            f"workflows/{workflow}/dispatches"
        ),
        headers=_github_headers(token),
        json={"ref": ref, "inputs": inputs},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolGatewayError(
            f"GitHub request failed with HTTP {response.status_code}"
        ) from exc

    data: dict[str, Any] = {}
    if response.content:
        try:
            parsed = response.json()
        except ValueError:
            parsed = {}
        if isinstance(parsed, dict):
            data = parsed
    run_id = data.get("workflow_run_id")
    request_id = response.headers.get("x-github-request-id")
    receipt = run_id or request_id
    if not receipt:
        raise ToolGatewayError("GitHub workflow dispatch returned no execution receipt")
    return {
        "workflow_run_id": run_id,
        "run_url": data.get("run_url"),
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": f"github-workflow:{receipt}",
            "provider": "github",
        },
    }


def render_deploy_service(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "Render")
    service_id = quote(_text(payload, "service_id"), safe="")
    request_body: dict[str, Any] = {}
    commit_id = payload.get("commit_id")
    if isinstance(commit_id, str) and commit_id.strip():
        request_body["commitId"] = commit_id.strip()
    clear_cache = bool(payload.get("clear_cache", False))
    request_body["clearCache"] = "clear" if clear_cache else "do_not_clear"

    response = httpx.post(
        f"https://api.render.com/v1/services/{service_id}/deploys",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "Render")
    deploy_id = data.get("id")
    if not deploy_id:
        raise ToolGatewayError("Render response did not include a deploy id")
    return {
        "deploy_id": str(deploy_id),
        "status": data.get("status"),
        "commit": data.get("commit"),
        "evidence": {
            "receipt_id": f"render-deploy:{deploy_id}",
            "provider": "render",
        },
    }


DEFAULT_EXTERNAL_ACTION_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "provider": "gmail",
        "action_name": "send-message",
        "name": "Gmail · Send message",
        "default_tool_slug": "gmail-send-message",
        "credential_slug": "gmail-tool-credential",
        "credential_name": "Gmail tool credential",
        "credential_env_locator": "SELDRUNE_GMAIL_TOOL_CREDENTIAL",
        "description": "Send an email using the authenticated Gmail mailbox.",
        "risk_level": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "from": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "provider": "github",
        "action_name": "create-issue",
        "name": "GitHub · Create issue",
        "default_tool_slug": "github-create-issue",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Create an issue in an authorized GitHub repository.",
        "risk_level": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["owner", "repo", "title"],
        },
    },
    {
        "provider": "github",
        "action_name": "comment",
        "name": "GitHub · Comment on issue or PR",
        "default_tool_slug": "github-comment",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Post a comment to an issue or pull request.",
        "risk_level": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "number": {"type": "integer"},
                "body": {"type": "string"},
            },
            "required": ["owner", "repo", "number", "body"],
        },
    },
    {
        "provider": "github",
        "action_name": "dispatch-workflow",
        "name": "GitHub · Dispatch workflow",
        "default_tool_slug": "github-dispatch-workflow",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Trigger an authorized workflow_dispatch workflow.",
        "risk_level": "high",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "workflow_id": {"type": "string"},
                "ref": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["owner", "repo", "workflow_id", "ref"],
        },
    },
    {
        "provider": "render",
        "action_name": "deploy-service",
        "name": "Render · Deploy service",
        "default_tool_slug": "render-deploy-service",
        "credential_slug": "render-api-key",
        "credential_name": "Render API key",
        "credential_env_locator": "SELDRUNE_RENDER_API_KEY",
        "description": "Trigger a deploy through the Render API and retain its deploy id.",
        "risk_level": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "commit_id": {"type": "string"},
                "clear_cache": {"type": "boolean"},
            },
            "required": ["service_id"],
        },
    },
)


def register_default_external_actions() -> None:
    register_external_action("gmail", "send-message", gmail_send_message)
    register_external_action("github", "create-issue", github_create_issue)
    register_external_action("github", "comment", github_comment)
    register_external_action("github", "dispatch-workflow", github_dispatch_workflow)
    register_external_action("render", "deploy-service", render_deploy_service)


def default_external_action_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_EXTERNAL_ACTION_CATALOG]
