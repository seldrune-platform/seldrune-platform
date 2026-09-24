from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership
from backend.app.models.task import Task
from backend.app.services.contract_recovery import advance_contract_with_recovery
from backend.app.services.contract_runner import (
    ContractRunnerError,
    advance_compiled_contract,
)
from backend.app.services.development_mission import (
    current_development_mission,
    queue_parallel_ready_stages,
    sync_development_mission_task,
)
from backend.app.services.one_go_controller import execute_one_go_controller


router = APIRouter(
    prefix="/organizations",
    tags=["development-mission"],
)

mission_read_dependency = require_org_permission(Permission.ORG_READ)
mission_manage_dependency = require_org_permission(Permission.ORG_MANAGE)
MissionReadDep = Annotated[Membership, Depends(mission_read_dependency)]
MissionManageDep = Annotated[Membership, Depends(mission_manage_dependency)]


class OneGoExecutionRequest(BaseModel):
    max_waves: int = Field(default=3, ge=1, le=10)
    max_tasks: int = Field(default=8, ge=1, le=50)
    recovery_rounds: int = Field(default=3, ge=1, le=5)


class ContractAdvanceRequest(BaseModel):
    max_steps: int = Field(default=12, ge=1, le=50)


class ContractRecoveryRequest(BaseModel):
    max_steps: int = Field(default=12, ge=1, le=50)
    max_rounds: int = Field(default=3, ge=1, le=5)


@router.get("/{organization_id}/development-mission")
def get_development_mission(
    organization_id: UUID,
    _membership: MissionReadDep,
    session: SessionDep,
) -> dict[str, Any]:
    mission, master_task = current_development_mission(
        session,
        organization_id=organization_id,
    )
    return {
        **mission,
        "organization_id": str(organization_id),
        "master_task_id": str(master_task.id) if master_task else None,
        "master_task_status": master_task.status if master_task else None,
        "one_go_execution": (
            (master_task.output_data or {}).get("one_go_execution")
            if master_task is not None
            else None
        ),
    }


@router.post("/{organization_id}/development-mission/sync")
def sync_development_mission(
    organization_id: UUID,
    _membership: MissionManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    task, mission, created = sync_development_mission_task(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    queued = queue_parallel_ready_stages(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        master_task=task,
    )
    return {
        **mission,
        "organization_id": str(organization_id),
        "master_task_id": str(task.id),
        "master_task_status": task.status,
        "created": created,
        "auto_queued_count": len(queued),
        "auto_queued_stage_ids": [
            (item.input_data or {}).get("cognitive_mission_stage_id")
            for item in queued
        ],
    }


@router.post("/{organization_id}/development-mission/queue-ready")
def queue_development_mission_wave(
    organization_id: UUID,
    _membership: MissionManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    master_task, mission, _ = sync_development_mission_task(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    queued = queue_parallel_ready_stages(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        master_task=master_task,
    )
    return {
        "mission_version": mission["version"],
        "master_task_id": str(master_task.id),
        "ready_stage_ids": mission["parallel_ready_stage_ids"],
        "queued_task_ids": [str(task.id) for task in queued],
        "queued_stage_ids": [
            (task.input_data or {}).get("cognitive_mission_stage_id")
            for task in queued
        ],
        "queued_count": len(queued),
        "execution_note": (
            "Ready stages are queued in parallel. They are not marked complete "
            "until execution produces verifiable evidence."
        ),
    }


@router.post(
    "/{organization_id}/development-mission/tasks/{task_id}/advance-contract"
)
def advance_development_mission_contract(
    organization_id: UUID,
    task_id: UUID,
    payload: ContractAdvanceRequest,
    _membership: MissionManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    task = session.get(Task, task_id)
    if task is None or task.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Development mission task not found",
        )
    input_data = task.input_data or {}
    if not input_data.get("cognitive_mission_stage_id"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task is not a cognitive mission stage",
        )

    try:
        return advance_compiled_contract(
            session,
            task=task,
            actor_user_id=current_user.id,
            max_steps=payload.max_steps,
        )
    except ContractRunnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{organization_id}/development-mission/tasks/{task_id}/recover-contract"
)
def recover_development_mission_contract(
    organization_id: UUID,
    task_id: UUID,
    payload: ContractRecoveryRequest,
    _membership: MissionManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    task = session.get(Task, task_id)
    if task is None or task.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Development mission task not found",
        )
    input_data = task.input_data or {}
    if not input_data.get("cognitive_mission_stage_id"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task is not a cognitive mission stage",
        )

    try:
        return advance_contract_with_recovery(
            session,
            task=task,
            actor_user_id=current_user.id,
            max_steps=payload.max_steps,
            max_rounds=payload.max_rounds,
        )
    except ContractRunnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/{organization_id}/development-mission/execute")
def execute_development_mission(
    organization_id: UUID,
    payload: OneGoExecutionRequest,
    _membership: MissionManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    try:
        return execute_one_go_controller(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            max_waves=payload.max_waves,
            max_tasks=payload.max_tasks,
            recovery_rounds=payload.recovery_rounds,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
