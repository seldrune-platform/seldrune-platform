from __future__ import annotations

import os
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.tasking import AgentStatus
from backend.app.core.tools import ApprovalMode, ToolRisk, ToolStatus
from backend.app.models.agent import Agent
from backend.app.models.secret_reference import SecretReference
from backend.app.models.tool_definition import ToolDefinition
from backend.app.services.agent_revisions import (
    capture_agent_revision,
    capture_snapshot_revision,
    configuration_snapshot,
)
from backend.app.services.audit import record_audit
from backend.app.services.external_actions import default_external_action_catalog
from backend.app.services.secret_vault import SecretVaultError, resolve_secret
from backend.app.services.tool_gateway import internal_action_catalog




_CREDENTIAL_ENV_ALIASES: dict[str, tuple[str, ...]] = {
    "gmail": ("SELDRUNE_GMAIL_TOOL_CREDENTIAL", "GMAIL_ACCESS_TOKEN"),
    "github": ("SELDRUNE_GITHUB_TOOL_TOKEN", "GITHUB_TOKEN"),
    "render": ("SELDRUNE_RENDER_API_KEY", "RENDER_API_KEY"),
}


def _credential_env_candidates(item: dict[str, Any]) -> tuple[str, ...]:
    primary = str(item["credential_env_locator"])
    aliases = _CREDENTIAL_ENV_ALIASES.get(str(item["provider"]), ())
    return tuple(dict.fromkeys((primary, *aliases)))


def _available_env_locator(item: dict[str, Any]) -> str | None:
    return next(
        (name for name in _credential_env_candidates(item) if os.getenv(name)),
        None,
    )


def _sync_agent_tool_grants(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    tools: list[ToolDefinition],
) -> list[str]:
    if not settings.agent_auto_grant_production_tools:
        return []

    active_slugs = sorted(
        {
            tool.slug
            for tool in tools
            if tool.status == ToolStatus.ACTIVE.value
        }
    )
    if not active_slugs:
        return []

    updated: list[str] = []
    agents = list(
        session.scalars(
            select(Agent).where(
                Agent.organization_id == organization_id,
                Agent.status == AgentStatus.ACTIVE.value,
            )
        )
    )
    for agent in agents:
        # None already means unrestricted access. Preserve that simpler policy.
        if agent.allowed_tool_slugs is None:
            continue
        merged = sorted(set(agent.allowed_tool_slugs) | set(active_slugs))
        if merged == sorted(agent.allowed_tool_slugs):
            continue
        previous_version = agent.version
        previous_snapshot = configuration_snapshot(agent)
        capture_snapshot_revision(
            session,
            agent=agent,
            version=previous_version,
            snapshot=previous_snapshot,
            actor_user_id=actor_user_id,
            change_kind="baseline",
        )
        agent.allowed_tool_slugs = merged
        agent.version += 1
        capture_agent_revision(
            session,
            agent=agent,
            actor_user_id=actor_user_id,
            change_kind="production_tool_grant",
        )
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="agent.production_tools_granted",
            resource_type="agent",
            resource_id=str(agent.id),
            details={
                "from_version": previous_version,
                "to_version": agent.version,
                "tool_count": len(merged),
            },
        )
        updated.append(agent.slug)
    return updated


def _catalog() -> list[dict[str, Any]]:
    return default_external_action_catalog()


def _secret_available(reference: SecretReference | None) -> bool:
    if reference is None or reference.status != "active":
        return False
    try:
        resolve_secret(reference)
    except SecretVaultError:
        return False
    return True


def _reference_by_slug(
    references: list[SecretReference],
    slug: str,
) -> SecretReference | None:
    return next((item for item in references if item.slug == slug), None)


def _matching_tool(
    tools: list[ToolDefinition],
    *,
    provider: str,
    action_name: str,
) -> ToolDefinition | None:
    return next(
        (
            item
            for item in tools
            if item.provider == provider and item.action_name == action_name
        ),
        None,
    )


def _matching_active_tool(
    tools: list[ToolDefinition],
    *,
    provider: str,
    action_name: str,
) -> ToolDefinition | None:
    tool = _matching_tool(
        tools,
        provider=provider,
        action_name=action_name,
    )
    if tool is None or tool.status != ToolStatus.ACTIVE.value:
        return None
    return tool


def configured_external_tool_status(
    session: Session,
    *,
    organization_id: UUID,
) -> dict[str, Any]:
    references = list(
        session.scalars(
            select(SecretReference).where(
                SecretReference.organization_id == organization_id
            )
        )
    )
    tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id
            )
        )
    )
    reference_by_id = {item.id: item for item in references}
    providers: dict[str, dict[str, Any]] = {}

    for item in _catalog():
        provider = str(item["provider"])
        credential_slug = str(item["credential_slug"])
        env_locator = str(item["credential_env_locator"])
        env_candidates = _credential_env_candidates(item)
        provider_status = providers.setdefault(
            provider,
            {
                "provider": provider,
                "credential_slug": credential_slug,
                "credential_env_locator": env_locator,
                "credential_env_locators": list(env_candidates),
                "active_credential_env_locator": None,
                "reference_id": None,
                "reference_status": "missing",
                "secret_available": False,
                "actions": [],
            },
        )

        reference = _reference_by_slug(references, credential_slug)
        if reference is not None:
            provider_status["reference_id"] = str(reference.id)
            provider_status["reference_status"] = reference.status
            provider_status["secret_available"] = _secret_available(reference)
            if reference.provider == "env" and provider_status["secret_available"]:
                provider_status["active_credential_env_locator"] = reference.locator
        else:
            available_locator = _available_env_locator(item)
            if available_locator:
                provider_status["reference_status"] = "discoverable_env"
                provider_status["secret_available"] = True
                provider_status["active_credential_env_locator"] = available_locator

        tool = _matching_active_tool(
            tools,
            provider=provider,
            action_name=str(item["action_name"]),
        )
        tool_secret_available = False
        if tool is not None and tool.credential_reference_id is not None:
            tool_secret_available = _secret_available(
                reference_by_id.get(tool.credential_reference_id)
            )

        provider_status["actions"].append(
            {
                "action_name": item["action_name"],
                "name": item["name"],
                "default_tool_slug": item["default_tool_slug"],
                "risk_level": item["risk_level"],
                "tool_id": str(tool.id) if tool is not None else None,
                "tool_slug": tool.slug if tool is not None else None,
                "tool_status": tool.status if tool is not None else "missing",
                "ready": bool(tool is not None and tool_secret_available),
            }
        )

    provider_list = list(providers.values())
    for provider in provider_list:
        provider["ready"] = bool(provider["actions"]) and all(
            action["ready"] for action in provider["actions"]
        )

    total_actions = sum(len(item["actions"]) for item in provider_list)
    ready_actions = sum(
        sum(bool(action["ready"]) for action in item["actions"])
        for item in provider_list
    )
    return {
        "providers": provider_list,
        "total_actions": total_actions,
        "ready_actions": ready_actions,
        "missing_actions": total_actions - ready_actions,
        "fully_ready": bool(total_actions) and ready_actions == total_actions,
    }


def ensure_configured_external_tools(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
) -> dict[str, Any]:
    references = list(
        session.scalars(
            select(SecretReference).where(
                SecretReference.organization_id == organization_id
            )
        )
    )
    tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id
            )
        )
    )
    created_references: list[str] = []
    created_tools: list[str] = []
    missing_env_locators: set[str] = set()

    for item in internal_action_catalog():
        existing = _matching_tool(
            tools,
            provider="internal",
            action_name=str(item["action_name"]),
        )
        if existing is not None:
            if existing.status != ToolStatus.ACTIVE.value:
                existing.status = ToolStatus.ACTIVE.value
            continue
        action_name = str(item["action_name"])
        tool = ToolDefinition(
            organization_id=organization_id,
            created_by_user_id=actor_user_id,
            name=str(item["name"]),
            slug=f"internal-{action_name}",
            description=str(item.get("description") or ""),
            provider="internal",
            action_name=action_name,
            credential_reference_id=None,
            status=ToolStatus.ACTIVE.value,
            risk_level=ToolRisk.LOW.value,
            approval_mode=ApprovalMode.NEVER.value,
            input_schema=dict(item.get("input_schema") or {}),
        )
        session.add(tool)
        session.flush()
        tools.append(tool)
        created_tools.append(tool.slug)
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="tool_bootstrap.internal_tool_created",
            resource_type="tool",
            resource_id=str(tool.id),
            details={"slug": tool.slug, "action_name": action_name},
        )

    catalog_by_credential: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _catalog():
        catalog_by_credential[str(item["credential_slug"])].append(item)

    references_by_slug = {item.slug: item for item in references}

    for credential_slug, items in catalog_by_credential.items():
        representative = items[0]
        reference = references_by_slug.get(credential_slug)
        env_locator = str(representative["credential_env_locator"])
        available_locator = _available_env_locator(representative)

        if reference is None:
            if available_locator is None:
                missing_env_locators.add(env_locator)
                continue
            reference = SecretReference(
                organization_id=organization_id,
                created_by_user_id=actor_user_id,
                name=str(representative["credential_name"]),
                slug=credential_slug,
                provider="env",
                locator=available_locator,
                status="active",
            )
            session.add(reference)
            session.flush()
            references.append(reference)
            references_by_slug[credential_slug] = reference
            created_references.append(reference.slug)
            record_audit(
                session,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="tool_bootstrap.secret_reference_created",
                resource_type="secret_reference",
                resource_id=str(reference.id),
                details={
                    "slug": reference.slug,
                    "provider": reference.provider,
                },
            )

        if not _secret_available(reference):
            if reference.provider == "env" and available_locator is not None:
                old_locator = reference.locator
                reference.locator = available_locator
                record_audit(
                    session,
                    organization_id=organization_id,
                    actor_user_id=actor_user_id,
                    action="tool_bootstrap.secret_reference_relinked",
                    resource_type="secret_reference",
                    resource_id=str(reference.id),
                    details={
                        "slug": reference.slug,
                        "from_locator": old_locator,
                        "to_locator": available_locator,
                    },
                )
            if not _secret_available(reference):
                missing_env_locators.add(reference.locator)
                continue

        for item in items:
            existing = _matching_tool(
                tools,
                provider=str(item["provider"]),
                action_name=str(item["action_name"]),
            )
            risk_level = str(item.get("risk_level") or ToolRisk.LOW.value)
            approval_mode = (
                ApprovalMode.ALWAYS.value
                if risk_level == ToolRisk.HIGH.value
                else ApprovalMode.NEVER.value
            )
            if existing is not None:
                changed: list[str] = []
                if existing.status != ToolStatus.ACTIVE.value:
                    existing.status = ToolStatus.ACTIVE.value
                    changed.append("status")
                if existing.credential_reference_id != reference.id:
                    existing.credential_reference_id = reference.id
                    changed.append("credential_reference_id")
                if existing.risk_level != risk_level:
                    existing.risk_level = risk_level
                    changed.append("risk_level")
                if existing.approval_mode != approval_mode:
                    existing.approval_mode = approval_mode
                    changed.append("approval_mode")
                expected_schema = dict(item.get("input_schema") or {})
                if existing.input_schema != expected_schema:
                    existing.input_schema = expected_schema
                    changed.append("input_schema")
                if existing.name != str(item["name"]):
                    existing.name = str(item["name"])
                    changed.append("name")
                if changed:
                    record_audit(
                        session,
                        organization_id=organization_id,
                        actor_user_id=actor_user_id,
                        action="tool_bootstrap.tool_repaired",
                        resource_type="tool",
                        resource_id=str(existing.id),
                        details={"slug": existing.slug, "changed_fields": changed},
                    )
                continue

            tool = ToolDefinition(
                organization_id=organization_id,
                created_by_user_id=actor_user_id,
                name=str(item["name"]),
                slug=str(item["default_tool_slug"]),
                description=str(item.get("description") or ""),
                provider=str(item["provider"]),
                action_name=str(item["action_name"]),
                credential_reference_id=reference.id,
                status=ToolStatus.ACTIVE.value,
                risk_level=risk_level,
                approval_mode=approval_mode,
                input_schema=dict(item.get("input_schema") or {}),
            )
            session.add(tool)
            session.flush()
            tools.append(tool)
            created_tools.append(tool.slug)
            record_audit(
                session,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="tool_bootstrap.tool_created",
                resource_type="tool",
                resource_id=str(tool.id),
                details={
                    "slug": tool.slug,
                    "provider": tool.provider,
                    "action_name": tool.action_name,
                    "credential_reference_id": str(reference.id),
                    "risk_level": tool.risk_level,
                    "approval_mode": tool.approval_mode,
                },
            )

    updated_agents = _sync_agent_tool_grants(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        tools=tools,
    )
    status = configured_external_tool_status(
        session,
        organization_id=organization_id,
    )
    return {
        **status,
        "created_references": created_references,
        "created_tools": created_tools,
        "missing_env_locators": sorted(missing_env_locators),
        "updated_agents": updated_agents,
    }
