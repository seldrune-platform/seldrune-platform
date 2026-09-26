from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.core.rbac import Permission
from backend.app.core.tools import ApprovalMode, ToolRisk, ToolRunStatus, ToolStatus
from backend.app.models.agent import Agent
from backend.app.models.membership import Membership
from backend.app.models.secret_reference import SecretReference
from backend.app.models.task import Task
from backend.app.models.tool_definition import ToolDefinition
from backend.app.models.tool_run import ToolRun
from backend.app.schemas.tooling import (
    ProviderCredentialPublic,
    ProviderCredentialUpsert,
    ToolDefinitionCreate,
    ToolDefinitionPublic,
    ToolRunCreate,
    ToolRunDecision,
    ToolRunPublic,
)
from backend.app.services.audit import record_audit
from backend.app.services.external_actions import default_external_action_catalog
from backend.app.services.provider_preflight import (
    preflight_configured_providers,
    preflight_provider_credential,
)
from backend.app.services.secret_vault import encrypt_secret_value, vault_locator
from backend.app.services.tool_bootstrap import (
    configured_external_tool_status,
    ensure_configured_external_tools,
)
from backend.app.services.tool_input_defaults import external_action_defaults_status
from backend.app.services.tool_gateway import (
    ToolGatewayError,
    allowed_internal_actions,
    internal_action_catalog,
    approve_tool_run,
    create_tool_run,
    execute_tool_run,
    external_action_registered,
    reject_tool_run,
)

router = APIRouter(prefix="/organizations", tags=["tools"])

run_dependency = require_org_permission(Permission.TOOLS_RUN)
manage_dependency = require_org_permission(Permission.TOOLS_MANAGE)
approve_dependency = require_org_permission(Permission.TOOLS_APPROVE)
ToolsRunDep = Annotated[Membership, Depends(run_dependency)]
ToolsManageDep = Annotated[Membership, Depends(manage_dependency)]
ToolsApproveDep = Annotated[Membership, Depends(approve_dependency)]


def _get_tool(session: SessionDep, organization_id: UUID, tool_id: UUID) -> ToolDefinition:
    tool = session.scalar(
        select(ToolDefinition).where(
            ToolDefinition.id == tool_id,
            ToolDefinition.organization_id == organization_id,
        )
    )
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    return tool


def _get_run(session: SessionDep, organization_id: UUID, run_id: UUID) -> ToolRun:
    run = session.scalar(
        select(ToolRun).where(
            ToolRun.id == run_id,
            ToolRun.organization_id == organization_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool run not found")
    return run


def _gateway_conflict(exc: ToolGatewayError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))




def _provider_catalog_item(provider: str) -> dict[str, Any]:
    item = next(
        (
            entry
            for entry in default_external_action_catalog()
            if entry["provider"] == provider
        ),
        None,
    )
    if item is None:
        raise HTTPException(status_code=422, detail="Unsupported built-in provider")
    return item


def _save_provider_credential(
    *,
    organization_id: UUID,
    provider: str,
    secret_value: str,
    actor_user_id: UUID,
    session: SessionDep,
) -> ProviderCredentialPublic:
    item = _provider_catalog_item(provider)
    credential_slug = str(item["credential_slug"])
    reference = session.scalar(
        select(SecretReference).where(
            SecretReference.organization_id == organization_id,
            SecretReference.slug == credential_slug,
        )
    )
    encrypted = encrypt_secret_value(secret_value)
    if reference is None:
        reference = SecretReference(
            organization_id=organization_id,
            created_by_user_id=actor_user_id,
            name=str(item["credential_name"]),
            slug=credential_slug,
            provider="vault",
            locator=vault_locator(),
            encrypted_value=encrypted,
            status="active",
        )
        session.add(reference)
        session.flush()
        action = "tool_bootstrap.provider_credential_created"
    else:
        reference.provider = "vault"
        reference.locator = vault_locator()
        reference.encrypted_value = encrypted
        reference.status = "active"
        action = "tool_bootstrap.provider_credential_rotated"

    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type="secret_reference",
        resource_id=str(reference.id),
        details={
            "provider": provider,
            "credential_slug": credential_slug,
        },
    )
    ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(reference)
    active_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.provider == provider,
                ToolDefinition.status == ToolStatus.ACTIVE.value,
            )
        )
    )
    return ProviderCredentialPublic(
        provider=provider,
        configured=True,
        credential_slug=credential_slug,
        reference_id=reference.id,
        tool_count=len(active_tools),
    )


def _quarantine_provider_credential(
    *,
    organization_id: UUID,
    provider: str,
    actor_user_id: UUID,
    session: SessionDep,
    reason: str,
) -> dict[str, Any]:
    item = _provider_catalog_item(provider)
    credential_slug = str(item["credential_slug"])
    reference = session.scalar(
        select(SecretReference).where(
            SecretReference.organization_id == organization_id,
            SecretReference.slug == credential_slug,
        )
    )
    if reference is None:
        return {
            "provider": provider,
            "quarantined": False,
            "disabled_tools": [],
            "secret_preserved": False,
            "detail": "No Seldrune credential is configured for this provider.",
        }

    disabled_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.provider == provider,
            )
        )
    )
    for tool in disabled_tools:
        tool.status = ToolStatus.DISABLED.value

    reference.status = "disabled"
    secret_preserved = bool(
        reference.encrypted_value is not None or reference.provider != "vault"
    )
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="tool_bootstrap.provider_credential_quarantined",
        resource_type="secret_reference",
        resource_id=str(reference.id),
        details={
            "provider": provider,
            "credential_slug": credential_slug,
            "reason": reason,
            "disabled_tools": sorted(tool.slug for tool in disabled_tools),
            "secret_preserved": secret_preserved,
        },
    )
    session.commit()
    return {
        "provider": provider,
        "quarantined": True,
        "disabled_tools": sorted(tool.slug for tool in disabled_tools),
        "secret_preserved": secret_preserved,
        "detail": (
            "Credential quarantined and provider tools disabled; stored secret preserved "
            "for later verified recovery."
        ),
    }


def _restore_provider_credential(
    *,
    organization_id: UUID,
    provider: str,
    actor_user_id: UUID,
    session: SessionDep,
) -> dict[str, Any]:
    item = _provider_catalog_item(provider)
    credential_slug = str(item["credential_slug"])
    reference = session.scalar(
        select(SecretReference).where(
            SecretReference.organization_id == organization_id,
            SecretReference.slug == credential_slug,
        )
    )
    if reference is None or reference.status == "active":
        return {
            "provider": provider,
            "restored": False,
            "active_tools": [],
        }

    reference.status = "active"
    provider_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.provider == provider,
            )
        )
    )
    for tool in provider_tools:
        tool.status = ToolStatus.ACTIVE.value
        tool.credential_reference_id = reference.id
    session.flush()

    status = ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    active_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.provider == provider,
                ToolDefinition.status == ToolStatus.ACTIVE.value,
            )
        )
    )
    restored = bool(active_tools)
    if not restored:
        reference.status = "disabled"
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=(
            "tool_bootstrap.provider_credential_restored"
            if restored
            else "tool_bootstrap.provider_credential_restore_failed"
        ),
        resource_type="secret_reference",
        resource_id=str(reference.id),
        details={
            "provider": provider,
            "credential_slug": credential_slug,
            "active_tools": sorted(tool.slug for tool in active_tools),
            "fully_ready": bool(status.get("fully_ready")),
        },
    )
    session.commit()
    return {
        "provider": provider,
        "restored": restored,
        "active_tools": sorted(tool.slug for tool in active_tools),
    }


def _disconnect_provider_credential(
    *,
    organization_id: UUID,
    provider: str,
    actor_user_id: UUID,
    session: SessionDep,
    reason: str,
) -> dict[str, Any]:
    item = _provider_catalog_item(provider)
    credential_slug = str(item["credential_slug"])
    reference = session.scalar(
        select(SecretReference).where(
            SecretReference.organization_id == organization_id,
            SecretReference.slug == credential_slug,
        )
    )
    if reference is None:
        return {
            "provider": provider,
            "removed": False,
            "disabled_tools": [],
            "detail": "No Seldrune credential is configured for this provider.",
        }

    disabled_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.provider == provider,
            )
        )
    )
    for tool in disabled_tools:
        tool.status = ToolStatus.DISABLED.value
        if tool.credential_reference_id == reference.id:
            tool.credential_reference_id = None

    reference.encrypted_value = None
    reference.status = "disabled"
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="tool_bootstrap.provider_credential_disconnected",
        resource_type="secret_reference",
        resource_id=str(reference.id),
        details={
            "provider": provider,
            "credential_slug": credential_slug,
            "reason": reason,
            "disabled_tools": sorted(tool.slug for tool in disabled_tools),
            "external_secret_not_deleted": reference.provider != "vault",
        },
    )
    session.commit()
    return {
        "provider": provider,
        "removed": True,
        "disabled_tools": sorted(tool.slug for tool in disabled_tools),
        "external_secret_not_deleted": reference.provider != "vault",
        "detail": (
            "Credential removed from the Seldrune vault and provider tools disabled."
            if reference.provider == "vault"
            else (
                "Credential reference disabled in Seldrune. Remove the underlying "
                "environment/AWS secret separately if it should no longer exist."
            )
        ),
    }


@router.post(
    "/{organization_id}/tool-bootstrap/credentials",
    response_model=ProviderCredentialPublic,
)
def upsert_provider_credential(
    organization_id: UUID,
    payload: ProviderCredentialUpsert,
    _membership: ToolsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ProviderCredentialPublic:
    return _save_provider_credential(
        organization_id=organization_id,
        provider=payload.provider,
        secret_value=payload.secret_value,
        actor_user_id=current_user.id,
        session=session,
    )


@router.post(
    "/{organization_id}/tool-bootstrap/credentials/verified",
    response_model=dict[str, Any],
)
def verify_and_store_provider_credential(
    organization_id: UUID,
    payload: ProviderCredentialUpsert,
    _membership: ToolsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    verification = preflight_provider_credential(
        payload.provider,
        payload.secret_value,
    )
    if not verification["verified"]:
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="tool_bootstrap.provider_credential_verification_failed",
            resource_type="organization",
            resource_id=str(organization_id),
            details={
                "provider": payload.provider,
                "status": verification["status"],
                "http_status": verification["http_status"],
            },
        )
        session.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Provider authentication failed; credential was not saved.",
                "verification": verification,
            },
        )

    saved = _save_provider_credential(
        organization_id=organization_id,
        provider=payload.provider,
        secret_value=payload.secret_value,
        actor_user_id=current_user.id,
        session=session,
    )
    return {
        "provider": saved.provider,
        "configured": saved.configured,
        "credential_slug": saved.credential_slug,
        "reference_id": str(saved.reference_id),
        "tool_count": saved.tool_count,
        "verification": verification,
    }


@router.delete(
    "/{organization_id}/tool-bootstrap/credentials/{provider}",
    response_model=dict[str, Any],
)
def disconnect_provider_credential(
    organization_id: UUID,
    provider: str,
    _membership: ToolsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    return _disconnect_provider_credential(
        organization_id=organization_id,
        provider=provider,
        actor_user_id=current_user.id,
        session=session,
        reason="owner_requested",
    )


@router.post(
    "/{organization_id}/tool-bootstrap/credentials/cleanup-invalid",
    response_model=dict[str, Any],
)
def cleanup_invalid_provider_credentials(
    organization_id: UUID,
    _membership: ToolsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    results = preflight_configured_providers(
        session,
        organization_id=organization_id,
    )
    invalid_providers = sorted(
        item["provider"]
        for item in results
        if item["status"] == "credential_invalid"
    )
    verified_providers = sorted(
        item["provider"]
        for item in results
        if bool(item.get("verified"))
    )

    quarantined: list[dict[str, Any]] = []
    for provider in invalid_providers:
        quarantined.append(
            _quarantine_provider_credential(
                organization_id=organization_id,
                provider=provider,
                actor_user_id=current_user.id,
                session=session,
                reason="remote_provider_rejected_credential",
            )
        )

    restored: list[dict[str, Any]] = []
    for provider in verified_providers:
        restored.append(
            _restore_provider_credential(
                organization_id=organization_id,
                provider=provider,
                actor_user_id=current_user.id,
                session=session,
            )
        )

    return {
        "checked": len(results),
        "invalid": invalid_providers,
        "removed": [],
        "quarantined": quarantined,
        "restored": restored,
    }


@router.post(
    "/{organization_id}/tool-bootstrap/preflight",
    response_model=dict[str, Any],
)
def preflight_tools(
    organization_id: UUID,
    _membership: ToolsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    results = preflight_configured_providers(
        session,
        organization_id=organization_id,
    )
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="tool_bootstrap.provider_preflight",
        resource_type="organization",
        resource_id=str(organization_id),
        details={
            "providers": [
                {
                    "provider": item["provider"],
                    "status": item["status"],
                    "verified": item["verified"],
                    "http_status": item["http_status"],
                }
                for item in results
            ]
        },
    )
    session.commit()
    return {
        "providers": results,
        "verified": sum(bool(item["verified"]) for item in results),
        "total": len(results),
    }


@router.get(
    "/{organization_id}/tool-bootstrap/status",
    response_model=dict[str, Any],
)
def get_tool_bootstrap_status(
    organization_id: UUID,
    _membership: ToolsRunDep,
    session: SessionDep,
) -> dict[str, Any]:
    return configured_external_tool_status(
        session,
        organization_id=organization_id,
    )


@router.post(
    "/{organization_id}/tool-bootstrap",
    response_model=dict[str, Any],
)
def bootstrap_tools(
    organization_id: UUID,
    _membership: ToolsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    result = ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    session.commit()
    return result


@router.get(
    "/{organization_id}/tool-defaults",
    response_model=list[dict[str, Any]],
)
def list_tool_defaults(
    organization_id: UUID,
    _membership: ToolsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[dict[str, Any]]:
    tools = list(
        session.scalars(
            select(ToolDefinition)
            .where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == ToolStatus.ACTIVE.value,
            )
            .order_by(ToolDefinition.name)
        )
    )
    return external_action_defaults_status(
        session,
        tools=tools,
        requested_by_user_id=current_user.id,
    )


@router.get(
    "/{organization_id}/tool-adapters",
    response_model=list[dict[str, Any]],
)
def list_tool_adapters(
    organization_id: UUID,
    _membership: ToolsRunDep,
) -> list[dict[str, Any]]:
    del organization_id
    internal = [
        {
            "provider": "internal",
            "action_name": item["action_name"],
            "name": item["name"],
            "description": item["description"],
            "risk_level": "low",
            "credential_required": False,
            "input_schema": item["input_schema"],
        }
        for item in internal_action_catalog()
    ]
    external = [
        {**item, "credential_required": True}
        for item in default_external_action_catalog()
    ]
    return [*internal, *external]


@router.post(
    "/{organization_id}/tools",
    response_model=ToolDefinitionPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_tool(
    organization_id: UUID,
    payload: ToolDefinitionCreate,
    _membership: ToolsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ToolDefinition:
    if payload.provider == "internal" and payload.action_name not in allowed_internal_actions():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"allowed_actions": allowed_internal_actions()},
        )
    if payload.provider == "internal" and payload.credential_reference_id is not None:
        raise HTTPException(status_code=422, detail="Internal tools cannot bind credentials")
    if (
        payload.provider != "internal"
        and not external_action_registered(payload.provider, payload.action_name)
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "External tool adapter is not registered: "
                f"{payload.provider}:{payload.action_name}"
            ),
        )
    if payload.credential_reference_id is not None:
        credential_reference = session.scalar(
            select(SecretReference).where(
                SecretReference.id == payload.credential_reference_id,
                SecretReference.organization_id == organization_id,
                SecretReference.status == "active",
            )
        )
        if credential_reference is None:
            raise HTTPException(status_code=422, detail="Credential reference is unavailable")
    risk_level = payload.risk_level
    risk_rank = {
        ToolRisk.LOW.value: 0,
        ToolRisk.MEDIUM.value: 1,
        ToolRisk.HIGH.value: 2,
    }
    adapter = next(
        (
            item
            for item in default_external_action_catalog()
            if item["provider"] == payload.provider
            and item["action_name"] == payload.action_name
        ),
        None,
    )
    if adapter is not None:
        if payload.credential_reference_id is None:
            raise HTTPException(
                status_code=422,
                detail="Built-in external adapters require a credential reference",
            )
        adapter_risk = str(adapter.get("risk_level") or ToolRisk.LOW.value)
        if risk_rank[adapter_risk] > risk_rank[risk_level]:
            risk_level = adapter_risk

    approval_mode = payload.approval_mode
    if risk_level == ToolRisk.HIGH.value:
        approval_mode = ApprovalMode.ALWAYS.value

    tool = ToolDefinition(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        provider=payload.provider,
        action_name=payload.action_name,
        credential_reference_id=payload.credential_reference_id,
        status=ToolStatus.ACTIVE.value,
        risk_level=risk_level,
        approval_mode=approval_mode,
        input_schema=payload.input_schema,
    )
    session.add(tool)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tool slug already exists",
        ) from exc
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="tool.created",
        resource_type="tool",
        resource_id=str(tool.id),
        details={
            "slug": tool.slug,
            "provider": tool.provider,
            "action_name": tool.action_name,
            "credential_reference_id": (
                str(tool.credential_reference_id) if tool.credential_reference_id else None
            ),
            "risk_level": tool.risk_level,
            "approval_mode": tool.approval_mode,
        },
    )
    session.commit()
    session.refresh(tool)
    return tool


@router.get("/{organization_id}/tools", response_model=list[ToolDefinitionPublic])
def list_tools(
    organization_id: UUID,
    _membership: ToolsRunDep,
    session: SessionDep,
) -> list[ToolDefinition]:
    return list(
        session.scalars(
            select(ToolDefinition)
            .where(ToolDefinition.organization_id == organization_id)
            .order_by(ToolDefinition.name)
        )
    )


@router.post(
    "/{organization_id}/tool-runs",
    response_model=ToolRunPublic,
    status_code=status.HTTP_201_CREATED,
)
def request_tool_run(
    organization_id: UUID,
    payload: ToolRunCreate,
    _membership: ToolsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ToolRun:
    tool = _get_tool(session, organization_id, payload.tool_id)
    agent: Agent | None = None
    if payload.task_id is not None:
        task = session.scalar(
            select(Task).where(
                Task.id == payload.task_id,
                Task.organization_id == organization_id,
            )
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if task.assigned_agent_id is not None:
            agent = session.scalar(
                select(Agent).where(
                    Agent.id == task.assigned_agent_id,
                    Agent.organization_id == organization_id,
                )
            )
            if agent is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Assigned agent not found",
                )
            if (
                agent.allowed_tool_slugs is not None
                and tool.slug not in agent.allowed_tool_slugs
            ):
                record_audit(
                    session,
                    organization_id=organization_id,
                    actor_user_id=current_user.id,
                    action="agent.tool_access_denied",
                    resource_type="agent",
                    resource_id=str(agent.id),
                    details={
                        "tool_id": str(tool.id),
                        "tool_slug": tool.slug,
                        "task_id": str(task.id),
                        "agent_version": agent.version,
                    },
                )
                session.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Tool is not allowed for the assigned agent",
                )
    try:
        run = create_tool_run(
            session,
            tool=tool,
            organization_id=organization_id,
            requested_by_user_id=current_user.id,
            input_data=payload.input_data,
            task_id=payload.task_id,
            agent_id=agent.id if agent else None,
        )
        if run.status == ToolRunStatus.APPROVED.value:
            run = execute_tool_run(
                session,
                run=run,
                tool=tool,
                actor_user_id=current_user.id,
            )
    except ToolGatewayError as exc:
        raise _gateway_conflict(exc) from exc
    return run


@router.get("/{organization_id}/tool-runs", response_model=list[ToolRunPublic])
def list_tool_runs(
    organization_id: UUID,
    _membership: ToolsRunDep,
    session: SessionDep,
) -> list[ToolRun]:
    return list(
        session.scalars(
            select(ToolRun)
            .where(ToolRun.organization_id == organization_id)
            .order_by(ToolRun.requested_at.desc())
        )
    )


@router.post(
    "/{organization_id}/tool-runs/{run_id}/approve",
    response_model=ToolRunPublic,
)
def approve_run(
    organization_id: UUID,
    run_id: UUID,
    _payload: ToolRunDecision,
    _membership: ToolsApproveDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ToolRun:
    run = _get_run(session, organization_id, run_id)
    tool = _get_tool(session, organization_id, run.tool_id)
    try:
        approve_tool_run(session, run=run, actor_user_id=current_user.id)
        return execute_tool_run(
            session,
            run=run,
            tool=tool,
            actor_user_id=current_user.id,
        )
    except ToolGatewayError as exc:
        raise _gateway_conflict(exc) from exc


@router.post(
    "/{organization_id}/tool-runs/{run_id}/reject",
    response_model=ToolRunPublic,
)
def reject_run(
    organization_id: UUID,
    run_id: UUID,
    payload: ToolRunDecision,
    _membership: ToolsApproveDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ToolRun:
    run = _get_run(session, organization_id, run_id)
    try:
        return reject_tool_run(
            session,
            run=run,
            actor_user_id=current_user.id,
            reason=payload.reason,
        )
    except ToolGatewayError as exc:
        raise _gateway_conflict(exc) from exc
