from typing import Annotated
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
    ToolDefinitionCreate,
    ToolDefinitionPublic,
    ToolRunCreate,
    ToolRunDecision,
    ToolRunPublic,
)
from backend.app.services.audit import record_audit
from backend.app.services.tool_gateway import (
    ToolGatewayError,
    allowed_internal_actions,
    approve_tool_run,
    create_tool_run,
    execute_tool_run,
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
    approval_mode = payload.approval_mode
    if payload.risk_level == ToolRisk.HIGH.value:
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
        risk_level=payload.risk_level,
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
            "credential_reference_id": str(tool.credential_reference_id) if tool.credential_reference_id else None,
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
