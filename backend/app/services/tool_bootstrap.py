from __future__ import annotations

import os
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.tools import ApprovalMode, ToolRisk, ToolStatus
from backend.app.models.secret_reference import SecretReference
from backend.app.models.tool_definition import ToolDefinition
from backend.app.services.audit import record_audit
from backend.app.services.external_actions import default_external_action_catalog
from backend.app.services.secret_vault import SecretVaultError, resolve_secret


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


def _matching_active_tool(
    tools: list[ToolDefinition],
    *,
    provider: str,
    action_name: str,
) -> ToolDefinition | None:
    return next(
        (
            item
            for item in tools
            if item.provider == provider
            and item.action_name == action_name
            and item.status == ToolStatus.ACTIVE.value
        ),
        None,
    )


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
        provider_status = providers.setdefault(
            provider,
            {
                "provider": provider,
                "credential_slug": credential_slug,
                "credential_env_locator": env_locator,
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
        elif os.getenv(env_locator):
            provider_status["reference_status"] = "discoverable_env"
            provider_status["secret_available"] = True

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

    catalog_by_credential: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _catalog():
        catalog_by_credential[str(item["credential_slug"])].append(item)

    references_by_slug = {item.slug: item for item in references}

    for credential_slug, items in catalog_by_credential.items():
        representative = items[0]
        reference = references_by_slug.get(credential_slug)
        env_locator = str(representative["credential_env_locator"])

        if reference is None:
            if not os.getenv(env_locator):
                missing_env_locators.add(env_locator)
                continue
            reference = SecretReference(
                organization_id=organization_id,
                created_by_user_id=actor_user_id,
                name=str(representative["credential_name"]),
                slug=credential_slug,
                provider="env",
                locator=env_locator,
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
            missing_env_locators.add(reference.locator)
            continue

        for item in items:
            existing = _matching_active_tool(
                tools,
                provider=str(item["provider"]),
                action_name=str(item["action_name"]),
            )
            if existing is not None:
                continue

            risk_level = str(item.get("risk_level") or ToolRisk.LOW.value)
            approval_mode = (
                ApprovalMode.ALWAYS.value
                if risk_level == ToolRisk.HIGH.value
                else ApprovalMode.NEVER.value
            )
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

    status = configured_external_tool_status(
        session,
        organization_id=organization_id,
    )
    return {
        **status,
        "created_references": created_references,
        "created_tools": created_tools,
        "missing_env_locators": sorted(missing_env_locators),
    }
