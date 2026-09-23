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



def github_repository_info(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    response = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=_github_headers(token),
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    repository_id = data.get("id")
    if not repository_id:
        raise ToolGatewayError("GitHub repository response did not include an id")
    return {
        "repository_id": repository_id,
        "full_name": data.get("full_name"),
        "default_branch": data.get("default_branch"),
        "private": bool(data.get("private")),
        "archived": bool(data.get("archived")),
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": f"github-repository:{repository_id}",
            "provider": "github",
        },
    }


def github_read_file(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    path = quote(_text(payload, "path"), safe="/")
    ref = _text(payload, "ref", required=False)
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    if ref:
        url += f"?ref={quote(ref, safe='/-._')}"
    response = httpx.get(
        url,
        headers=_github_headers(token),
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    if data.get("type") != "file":
        raise ToolGatewayError("GitHub content path is not a file")
    encoded = data.get("content")
    decoded: str | None = None
    if data.get("encoding") == "base64" and isinstance(encoded, str):
        try:
            raw = base64.b64decode(encoded, validate=False)
            decoded = raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            decoded = None
    if decoded is not None and len(decoded) > 200_000:
        decoded = decoded[:200_000]
    return {
        "path": data.get("path"),
        "sha": data.get("sha"),
        "size": data.get("size"),
        "content": decoded,
        "content_truncated": bool(decoded is not None and data.get("size", 0) > 200_000),
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": f"github-file:{data.get('sha') or path}",
            "provider": "github",
        },
    }


def github_create_branch(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    branch = _text(payload, "branch")
    ref = _text(payload, "ref")
    if branch in {"main", "master"}:
        raise ToolGatewayError("Refusing to create or overwrite a protected default branch")
    base_response = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{quote(ref, safe='/-._')}",
        headers=_github_headers(token),
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    base = _json_response(base_response, "GitHub")
    target = base.get("object") or {}
    sha = target.get("sha") if isinstance(target, dict) else None
    if not sha:
        raise ToolGatewayError("GitHub base branch response did not include a commit sha")
    response = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/git/refs",
        headers=_github_headers(token),
        json={"ref": f"refs/heads/{branch}", "sha": sha},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    created_ref = data.get("ref")
    object_data = data.get("object") or {}
    created_sha = object_data.get("sha") if isinstance(object_data, dict) else None
    return {
        "branch": branch,
        "ref": created_ref,
        "sha": created_sha or sha,
        "base_ref": ref,
        "evidence": {
            "receipt_id": f"github-branch:{created_sha or sha}:{branch}",
            "provider": "github",
        },
    }


def github_upsert_file(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    path = quote(_text(payload, "path"), safe="/")
    branch = _text(payload, "branch")
    base_ref = _text(payload, "base_ref", required=False)
    if branch in {"main", "master"} or (base_ref and branch == base_ref):
        raise ToolGatewayError(
            "Direct file writes to the protected/default branch are not allowed; "
            "create a feature branch and open a pull request"
        )
    message = _text(payload, "message")
    content = _text(payload, "content")
    existing_sha: str | None = None
    lookup = httpx.get(
        (
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            f"?ref={quote(branch, safe='/-._')}"
        ),
        headers=_github_headers(token),
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    if lookup.status_code == 200:
        existing = _json_response(lookup, "GitHub")
        raw_sha = existing.get("sha")
        existing_sha = str(raw_sha) if raw_sha else None
    elif lookup.status_code != 404:
        _json_response(lookup, "GitHub")

    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        body["sha"] = existing_sha

    response = httpx.put(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=_github_headers(token),
        json=body,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    commit = data.get("commit") or {}
    content_meta = data.get("content") or {}
    commit_sha = commit.get("sha") if isinstance(commit, dict) else None
    content_sha = content_meta.get("sha") if isinstance(content_meta, dict) else None
    if not commit_sha:
        raise ToolGatewayError("GitHub file update response did not include a commit sha")
    return {
        "path": content_meta.get("path") if isinstance(content_meta, dict) else None,
        "branch": branch,
        "commit_sha": commit_sha,
        "content_sha": content_sha,
        "updated_existing": existing_sha is not None,
        "html_url": content_meta.get("html_url") if isinstance(content_meta, dict) else None,
        "evidence": {
            "receipt_id": f"github-commit:{commit_sha}",
            "provider": "github",
        },
    }


def github_get_pull_request(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    pull_number = _integer(payload, "pull_number")
    response = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}",
        headers=_github_headers(token),
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    pull_id = data.get("id")
    if not pull_id:
        raise ToolGatewayError("GitHub pull request response did not include an id")
    return {
        "pull_request_id": pull_id,
        "number": data.get("number"),
        "state": data.get("state"),
        "merged": bool(data.get("merged")),
        "mergeable": data.get("mergeable"),
        "draft": bool(data.get("draft")),
        "head_sha": (
            (data.get("head") or {}).get("sha")
            if isinstance(data.get("head"), dict)
            else None
        ),
        "base_ref": (
            (data.get("base") or {}).get("ref")
            if isinstance(data.get("base"), dict)
            else None
        ),
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": f"github-pull-state:{pull_id}:{data.get('updated_at') or pull_number}",
            "provider": "github",
        },
    }


def github_workflow_run_status(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    run_id = _integer(payload, "run_id")
    response = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}",
        headers=_github_headers(token),
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    provider_run_id = data.get("id")
    if not provider_run_id:
        raise ToolGatewayError("GitHub workflow response did not include a run id")
    return {
        "run_id": provider_run_id,
        "name": data.get("name"),
        "status": data.get("status"),
        "conclusion": data.get("conclusion"),
        "head_sha": data.get("head_sha"),
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": (
                f"github-workflow-state:{provider_run_id}:"
                f"{data.get('updated_at') or data.get('status') or 'unknown'}"
            ),
            "provider": "github",
        },
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


def github_create_pull_request(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    title = _text(payload, "title")
    head = _text(payload, "head")
    base = _text(payload, "base")
    request_body: dict[str, Any] = {
        "title": title,
        "head": head,
        "base": base,
        "draft": bool(payload.get("draft", False)),
    }
    body = _text(payload, "body", required=False)
    if body:
        request_body["body"] = body

    response = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        headers=_github_headers(token),
        json=request_body,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    pull_id = data.get("id")
    if not pull_id:
        raise ToolGatewayError("GitHub response did not include a pull request id")
    return {
        "pull_request_id": pull_id,
        "number": data.get("number"),
        "state": data.get("state"),
        "html_url": data.get("html_url"),
        "evidence": {
            "receipt_id": f"github-pull:{pull_id}",
            "provider": "github",
        },
    }


def github_merge_pull_request(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "GitHub")
    owner = quote(_text(payload, "owner"), safe="")
    repo = quote(_text(payload, "repo"), safe="")
    pull_number = _integer(payload, "pull_number")
    request_body: dict[str, Any] = {}

    merge_method = payload.get("merge_method")
    if merge_method is not None:
        if merge_method not in {"merge", "squash", "rebase"}:
            raise ToolGatewayError("merge_method must be merge, squash, or rebase")
        request_body["merge_method"] = merge_method
    for key in ("commit_title", "commit_message", "sha"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            request_body[key] = value.strip()

    response = httpx.put(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/merge",
        headers=_github_headers(token),
        json=request_body,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "GitHub")
    if data.get("merged") is not True:
        raise ToolGatewayError(
            str(data.get("message") or "GitHub did not merge the pull request")
        )
    merge_sha = data.get("sha")
    receipt = merge_sha or str(pull_number)
    return {
        "pull_number": pull_number,
        "merged": True,
        "sha": merge_sha,
        "message": data.get("message"),
        "evidence": {
            "receipt_id": f"github-merge:{receipt}",
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



def render_deploy_status(
    payload: dict[str, Any],
    credential: str | None,
) -> dict[str, Any]:
    token = _credential(credential, "Render")
    service_id = quote(_text(payload, "service_id"), safe="")
    deploy_id = quote(_text(payload, "deploy_id"), safe="")
    response = httpx.get(
        f"https://api.render.com/v1/services/{service_id}/deploys/{deploy_id}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    data = _json_response(response, "Render")
    provider_deploy_id = data.get("id")
    if not provider_deploy_id:
        raise ToolGatewayError("Render deploy response did not include a deploy id")
    return {
        "deploy_id": str(provider_deploy_id),
        "status": data.get("status"),
        "commit": data.get("commit"),
        "created_at": data.get("createdAt"),
        "updated_at": data.get("updatedAt"),
        "evidence": {
            "receipt_id": (
                f"render-deploy-state:{provider_deploy_id}:"
                f"{data.get('updatedAt') or data.get('status') or 'unknown'}"
            ),
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
        "action_name": "repository-info",
        "name": "GitHub · Repository info",
        "default_tool_slug": "github-repository-info",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Verify the authorized repository and read its default branch metadata.",
        "risk_level": "low",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "provider": "github",
        "action_name": "read-file",
        "name": "GitHub · Read file",
        "default_tool_slug": "github-read-file",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Read a UTF-8 repository file from an authorized ref.",
        "risk_level": "low",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string"},
                "ref": {"type": "string"},
            },
            "required": ["owner", "repo", "path", "ref"],
        },
    },
    {
        "provider": "github",
        "action_name": "create-branch",
        "name": "GitHub · Create branch",
        "default_tool_slug": "github-create-branch",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Create a feature branch from an authorized repository ref.",
        "risk_level": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "branch": {"type": "string"},
                "ref": {"type": "string"},
            },
            "required": ["owner", "repo", "branch", "ref"],
        },
    },
    {
        "provider": "github",
        "action_name": "upsert-file",
        "name": "GitHub · Upsert file on feature branch",
        "default_tool_slug": "github-upsert-file",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": (
            "Create or update a UTF-8 repository file on a non-default feature branch. "
            "Direct writes to main/master are rejected."
        ),
        "risk_level": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string"},
                "branch": {"type": "string"},
                "message": {"type": "string"},
                "content": {"type": "string"},
                "base_ref": {"type": "string"},
            },
            "required": [
                "owner",
                "repo",
                "path",
                "branch",
                "message",
                "content",
            ],
        },
    },
    {
        "provider": "github",
        "action_name": "get-pull-request",
        "name": "GitHub · Get pull request",
        "default_tool_slug": "github-get-pull-request",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Inspect pull-request state and merge readiness.",
        "risk_level": "low",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pull_number": {"type": "integer"},
            },
            "required": ["owner", "repo", "pull_number"],
        },
    },
    {
        "provider": "github",
        "action_name": "workflow-run-status",
        "name": "GitHub · Workflow run status",
        "default_tool_slug": "github-workflow-run-status",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Read the current state and conclusion of a GitHub Actions run.",
        "risk_level": "low",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "run_id": {"type": "integer"},
            },
            "required": ["owner", "repo", "run_id"],
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
        "action_name": "create-pull-request",
        "name": "GitHub · Create pull request",
        "default_tool_slug": "github-create-pull-request",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Create a pull request in an authorized GitHub repository.",
        "risk_level": "medium",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "head": {"type": "string"},
                "base": {"type": "string"},
                "body": {"type": "string"},
                "draft": {"type": "boolean"},
            },
            "required": ["owner", "repo", "title", "head", "base"],
        },
    },
    {
        "provider": "github",
        "action_name": "merge-pull-request",
        "name": "GitHub · Merge pull request",
        "default_tool_slug": "github-merge-pull-request",
        "credential_slug": "github-tool-token",
        "credential_name": "GitHub tool token",
        "credential_env_locator": "SELDRUNE_GITHUB_TOOL_TOKEN",
        "description": "Merge an authorized GitHub pull request.",
        "risk_level": "high",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pull_number": {"type": "integer"},
                "merge_method": {
                    "type": "string",
                    "enum": ["merge", "squash", "rebase"],
                },
                "commit_title": {"type": "string"},
                "commit_message": {"type": "string"},
                "sha": {"type": "string"},
            },
            "required": ["owner", "repo", "pull_number"],
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
        "action_name": "deploy-status",
        "name": "Render · Deploy status",
        "default_tool_slug": "render-deploy-status",
        "credential_slug": "render-api-key",
        "credential_name": "Render API key",
        "credential_env_locator": "SELDRUNE_RENDER_API_KEY",
        "description": "Verify the current state of a Render deploy using its deploy id.",
        "risk_level": "low",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "deploy_id": {"type": "string"},
            },
            "required": ["service_id", "deploy_id"],
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
    register_external_action("github", "repository-info", github_repository_info)
    register_external_action("github", "read-file", github_read_file)
    register_external_action("github", "create-branch", github_create_branch)
    register_external_action("github", "upsert-file", github_upsert_file)
    register_external_action("github", "get-pull-request", github_get_pull_request)
    register_external_action(
        "github",
        "workflow-run-status",
        github_workflow_run_status,
    )
    register_external_action("github", "create-issue", github_create_issue)
    register_external_action("github", "comment", github_comment)
    register_external_action("github", "create-pull-request", github_create_pull_request)
    register_external_action("github", "merge-pull-request", github_merge_pull_request)
    register_external_action("github", "dispatch-workflow", github_dispatch_workflow)
    register_external_action("render", "deploy-status", render_deploy_status)
    register_external_action("render", "deploy-service", render_deploy_service)


def default_external_action_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_EXTERNAL_ACTION_CATALOG]
