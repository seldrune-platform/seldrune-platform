from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.tool_definition import ToolDefinition
from backend.app.models.user import User


def _non_empty(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def external_action_input_defaults(
    session: Session,
    *,
    tool: ToolDefinition,
    requested_by_user_id: UUID,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    provider = tool.provider.lower()
    action = tool.action_name

    if provider == "gmail" and action == "send-message":
        user = session.get(User, requested_by_user_id)
        if user is not None and user.is_active:
            defaults["to"] = user.email

    if provider == "github":
        owner = _non_empty(settings.github_default_owner)
        repo = _non_empty(settings.github_default_repo)
        ref = _non_empty(settings.github_default_ref)
        if owner:
            defaults["owner"] = owner
        if repo:
            defaults["repo"] = repo
        if action == "dispatch-workflow" and ref:
            defaults["ref"] = ref
        if action == "create-pull-request" and ref:
            defaults["base"] = ref

    if provider == "render" and action == "deploy-service":
        service_id = _non_empty(settings.render_default_service_id)
        if service_id:
            defaults["service_id"] = service_id

    return defaults


def apply_external_action_input_defaults(
    session: Session,
    *,
    tool: ToolDefinition,
    requested_by_user_id: UUID,
    input_data: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if tool.provider == "internal":
        return dict(input_data), []

    result = dict(input_data)
    defaults = external_action_input_defaults(
        session,
        tool=tool,
        requested_by_user_id=requested_by_user_id,
    )
    applied: list[str] = []
    for key, value in defaults.items():
        current = result.get(key)
        if current is None or (isinstance(current, str) and not current.strip()):
            result[key] = value
            applied.append(key)
    return result, sorted(applied)


def external_action_default_fields(
    session: Session,
    *,
    tool: ToolDefinition,
    requested_by_user_id: UUID,
) -> list[str]:
    return sorted(
        external_action_input_defaults(
            session,
            tool=tool,
            requested_by_user_id=requested_by_user_id,
        )
    )


def external_action_defaults_status(
    session: Session,
    *,
    tools: list[ToolDefinition],
    requested_by_user_id: UUID,
) -> list[dict[str, Any]]:
    status: list[dict[str, Any]] = []
    for tool in tools:
        if tool.provider == "internal":
            continue
        defaults = external_action_input_defaults(
            session,
            tool=tool,
            requested_by_user_id=requested_by_user_id,
        )
        status.append(
            {
                "tool_slug": tool.slug,
                "provider": tool.provider,
                "action_name": tool.action_name,
                "defaulted_fields": sorted(defaults),
            }
        )
    return status
