from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.tools import ApprovalMode, ToolRisk, ToolRunStatus, ToolStatus
from backend.app.models.secret_reference import SecretReference
from backend.app.models.tool_definition import ToolDefinition
from backend.app.models.tool_run import ToolRun
from backend.app.services.audit import record_audit
from backend.app.services.secret_vault import SecretVaultError, resolve_secret
from backend.app.services.tool_input_defaults import apply_external_action_input_defaults


class ToolGatewayError(RuntimeError):
    pass


class ToolExecutionEvidenceError(ToolGatewayError):
    """Raised when an external action does not return verifiable execution evidence."""


_EXTERNAL_ACTIONS: dict[
    tuple[str, str], Callable[[dict[str, Any], str | None], dict[str, Any]]
] = {}


def register_external_action(
    provider: str,
    action_name: str,
    handler: Callable[[dict[str, Any], str | None], dict[str, Any]],
) -> None:
    """Register a governed provider adapter at application startup."""
    key = (provider.strip().lower(), action_name.strip())
    if not key[0] or key[0] == "internal" or not key[1]:
        raise ToolGatewayError("External action requires a non-internal provider and action name")
    _EXTERNAL_ACTIONS[key] = handler


def external_action_registered(provider: str, action_name: str) -> bool:
    return (provider.strip().lower(), action_name.strip()) in _EXTERNAL_ACTIONS


def registered_external_actions() -> tuple[tuple[str, str], ...]:
    return tuple(sorted(_EXTERNAL_ACTIONS))


def _resolve_action(tool: ToolDefinition) -> Callable[..., dict[str, Any]]:
    if tool.provider == "internal":
        action = _INTERNAL_ACTIONS.get(tool.action_name)
    else:
        action = _EXTERNAL_ACTIONS.get((tool.provider.lower(), tool.action_name))
    if action is None:
        raise ToolGatewayError(
            f"Tool adapter is not registered: {tool.provider}:{tool.action_name}"
        )
    return action


def _validate_external_evidence(tool: ToolDefinition, output: dict[str, Any]) -> None:
    if tool.provider == "internal":
        return
    evidence = output.get("evidence") if isinstance(output, dict) else None
    if not isinstance(evidence, dict) or not evidence.get("receipt_id"):
        raise ToolExecutionEvidenceError(
            "External action did not return execution evidence with receipt_id"
        )


def _echo(payload: dict[str, Any]) -> dict[str, Any]:
    return {"echo": payload}


def _text_stats(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text", "")
    if not isinstance(text, str):
        raise ToolGatewayError("text must be a string")
    return {
        "characters": len(text),
        "words": len(text.split()),
        "lines": len(text.splitlines()) if text else 0,
    }


def _json_validate(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("value")
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            return {
                "valid": False,
                "error": exc.msg,
                "line": exc.lineno,
                "column": exc.colno,
            }
    elif isinstance(value, (dict, list, int, float, bool)) or value is None:
        parsed = value
    else:
        raise ToolGatewayError("value must be JSON-compatible or a JSON string")
    return {
        "valid": True,
        "type": type(parsed).__name__,
        "value": parsed,
    }


def _json_pretty(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("value")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ToolGatewayError(f"Invalid JSON: {exc.msg}") from exc
    try:
        rendered = json.dumps(
            value,
            indent=2,
            sort_keys=bool(payload.get("sort_keys", False)),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise ToolGatewayError("value is not JSON serializable") from exc
    return {"text": rendered}


def _sha256_text(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    if not isinstance(text, str):
        raise ToolGatewayError("text must be a string")
    return {
        "algorithm": "sha256",
        "digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def _base64_encode(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    if not isinstance(text, str):
        raise ToolGatewayError("text must be a string")
    return {"base64": base64.b64encode(text.encode("utf-8")).decode("ascii")}


def _base64_decode(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("base64")
    if not isinstance(value, str):
        raise ToolGatewayError("base64 must be a string")
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ToolGatewayError("base64 must contain valid UTF-8 data") from exc
    return {"text": decoded}


def _text_replace(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    old = payload.get("old")
    new = payload.get("new", "")
    if not isinstance(text, str) or not isinstance(old, str) or not isinstance(new, str):
        raise ToolGatewayError("text, old, and new must be strings")
    if not old:
        raise ToolGatewayError("old must be a non-empty string")
    count_value = payload.get("count")
    count = -1
    if count_value is not None:
        try:
            count = int(count_value)
        except (TypeError, ValueError) as exc:
            raise ToolGatewayError("count must be an integer") from exc
        if count < 0:
            raise ToolGatewayError("count must be zero or positive")
    result = text.replace(old, new, count)
    return {
        "text": result,
        "replacements": text.count(old) if count < 0 else min(text.count(old), count),
    }


def _csv_preview(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    if not isinstance(text, str):
        raise ToolGatewayError("text must be a string")
    delimiter = payload.get("delimiter", ",")
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ToolGatewayError("delimiter must be one character")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows: list[list[str]] = []
    for index, row in enumerate(reader):
        if index >= 100:
            break
        rows.append(row)
    return {
        "rows": rows,
        "row_count_previewed": len(rows),
        "truncated": len(text.splitlines()) > len(rows),
    }


_INTERNAL_ACTIONS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "echo": _echo,
    "text-stats": _text_stats,
    "json-validate": _json_validate,
    "json-pretty": _json_pretty,
    "sha256-text": _sha256_text,
    "base64-encode": _base64_encode,
    "base64-decode": _base64_decode,
    "text-replace": _text_replace,
    "csv-preview": _csv_preview,
}


_INTERNAL_ACTION_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "action_name": "echo",
        "name": "Internal · Echo",
        "description": "Return structured input unchanged for deterministic handoffs.",
        "input_schema": {"type": "object"},
    },
    {
        "action_name": "text-stats",
        "name": "Internal · Text statistics",
        "description": "Count characters, words, and lines in text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "action_name": "json-validate",
        "name": "Internal · JSON validate",
        "description": "Validate and parse JSON-compatible data.",
        "input_schema": {
            "type": "object",
            "properties": {"value": {}},
            "required": ["value"],
        },
    },
    {
        "action_name": "json-pretty",
        "name": "Internal · JSON format",
        "description": "Render JSON-compatible data as readable deterministic text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "value": {},
                "sort_keys": {"type": "boolean"},
            },
            "required": ["value"],
        },
    },
    {
        "action_name": "sha256-text",
        "name": "Internal · SHA-256",
        "description": "Calculate a SHA-256 digest for UTF-8 text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "action_name": "base64-encode",
        "name": "Internal · Base64 encode",
        "description": "Encode UTF-8 text as Base64.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "action_name": "base64-decode",
        "name": "Internal · Base64 decode",
        "description": "Decode Base64 data that represents UTF-8 text.",
        "input_schema": {
            "type": "object",
            "properties": {"base64": {"type": "string"}},
            "required": ["base64"],
        },
    },
    {
        "action_name": "text-replace",
        "name": "Internal · Text replace",
        "description": "Replace literal text deterministically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["text", "old", "new"],
        },
    },
    {
        "action_name": "csv-preview",
        "name": "Internal · CSV preview",
        "description": "Parse up to 100 CSV rows for structured inspection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "delimiter": {"type": "string"},
            },
            "required": ["text"],
        },
    },
)


def internal_action_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in _INTERNAL_ACTION_CATALOG]


def allowed_internal_actions() -> tuple[str, ...]:
    return tuple(sorted(_INTERNAL_ACTIONS))


def requires_approval(tool: ToolDefinition) -> bool:
    return (
        tool.approval_mode == ApprovalMode.ALWAYS.value
        or tool.risk_level == ToolRisk.HIGH.value
    )


def create_tool_run(
    session: Session,
    *,
    tool: ToolDefinition,
    organization_id: UUID,
    requested_by_user_id: UUID,
    input_data: dict[str, Any],
    task_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> ToolRun:
    if tool.organization_id != organization_id:
        raise ToolGatewayError("Tool does not belong to this organization")
    if tool.status != ToolStatus.ACTIVE.value:
        raise ToolGatewayError("Tool is disabled")
    _resolve_action(tool)

    status = (
        ToolRunStatus.PENDING_APPROVAL
        if requires_approval(tool)
        else ToolRunStatus.APPROVED
    )
    normalized_input, defaults_applied = apply_external_action_input_defaults(
        session,
        tool=tool,
        requested_by_user_id=requested_by_user_id,
        input_data=input_data,
    )
    run = ToolRun(
        organization_id=organization_id,
        tool_id=tool.id,
        task_id=task_id,
        agent_id=agent_id,
        requested_by_user_id=requested_by_user_id,
        status=status.value,
        input_data=normalized_input,
    )
    session.add(run)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=requested_by_user_id,
        action="tool.run.requested",
        resource_type="tool_run",
        resource_id=str(run.id),
        details={
            "tool_id": str(tool.id),
            "agent_id": str(agent_id) if agent_id else None,
            "status": run.status,
            "risk_level": tool.risk_level,
            "defaults_applied": defaults_applied,
        },
    )
    session.commit()
    session.refresh(run)
    return run


def execute_tool_run(
    session: Session,
    *,
    run: ToolRun,
    tool: ToolDefinition,
    actor_user_id: UUID,
) -> ToolRun:
    if run.status != ToolRunStatus.APPROVED.value:
        raise ToolGatewayError("Tool run is not approved for execution")
    action = _resolve_action(tool)

    run.status = ToolRunStatus.RUNNING.value
    run.started_at = datetime.now(UTC)
    session.commit()

    try:
        if tool.provider == "internal":
            output = action(run.input_data)
        else:
            credential: str | None = None
            if tool.credential_reference_id is not None:
                reference = session.get(SecretReference, tool.credential_reference_id)
                if reference is None or reference.organization_id != run.organization_id:
                    raise ToolGatewayError("Credential reference is unavailable")
                try:
                    credential = resolve_secret(reference)
                except SecretVaultError as exc:
                    raise ToolGatewayError("Credential could not be resolved") from exc
            output = action(run.input_data, credential)
        _validate_external_evidence(tool, output)
    except ToolGatewayError as exc:
        error_message = str(exc)
    except Exception as exc:
        error_message = f"Tool adapter failed: {type(exc).__name__}"
    else:
        error_message = None

    if error_message is not None:
        run.status = ToolRunStatus.FAILED.value
        run.error_message = error_message
        run.completed_at = datetime.now(UTC)
        record_audit(
            session,
            organization_id=run.organization_id,
            actor_user_id=actor_user_id,
            action="tool.run.failed",
            resource_type="tool_run",
            resource_id=str(run.id),
            details={"tool_id": str(tool.id), "error": error_message},
        )
        session.commit()
        session.refresh(run)
        return run

    run.status = ToolRunStatus.SUCCEEDED.value
    run.output_data = output
    run.completed_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=run.organization_id,
        actor_user_id=actor_user_id,
        action="tool.run.succeeded",
        resource_type="tool_run",
        resource_id=str(run.id),
        details={"tool_id": str(tool.id), "action_name": tool.action_name},
    )
    session.commit()
    session.refresh(run)
    return run


def approve_tool_run(
    session: Session,
    *,
    run: ToolRun,
    actor_user_id: UUID,
) -> ToolRun:
    if run.status != ToolRunStatus.PENDING_APPROVAL.value:
        raise ToolGatewayError("Tool run is not awaiting approval")
    run.status = ToolRunStatus.APPROVED.value
    run.decided_by_user_id = actor_user_id
    run.decided_at = datetime.now(UTC)
    record_audit(
        session,
        organization_id=run.organization_id,
        actor_user_id=actor_user_id,
        action="tool.run.approved",
        resource_type="tool_run",
        resource_id=str(run.id),
        details={"tool_id": str(run.tool_id)},
    )
    session.commit()
    session.refresh(run)
    return run


def reject_tool_run(
    session: Session,
    *,
    run: ToolRun,
    actor_user_id: UUID,
    reason: str | None = None,
) -> ToolRun:
    if run.status != ToolRunStatus.PENDING_APPROVAL.value:
        raise ToolGatewayError("Tool run is not awaiting approval")
    run.status = ToolRunStatus.REJECTED.value
    run.decided_by_user_id = actor_user_id
    run.decided_at = datetime.now(UTC)
    run.completed_at = run.decided_at
    run.error_message = reason
    record_audit(
        session,
        organization_id=run.organization_id,
        actor_user_id=actor_user_id,
        action="tool.run.rejected",
        resource_type="tool_run",
        resource_id=str(run.id),
        details={"tool_id": str(run.tool_id), "reason": reason},
    )
    session.commit()
    session.refresh(run)
    return run
