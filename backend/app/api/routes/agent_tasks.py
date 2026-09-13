from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.core.rbac import Permission
from backend.app.core.tasking import AgentStatus, TaskStatus
from backend.app.models.agent import Agent
from backend.app.models.membership import Membership
from backend.app.models.task import Task, TaskEvent
from backend.app.schemas.agent_task import (
    AgentCreate,
    AgentPublic,
    TaskAssignRequest,
    TaskCreate,
    TaskEventPublic,
    TaskPublic,
    TaskTransitionRequest,
)
from backend.app.services.audit import record_audit
from backend.app.services.task_engine import TaskTransitionError, transition_task

router = APIRouter(prefix="/organizations", tags=["agents", "tasks"])

agents_run_dependency = require_org_permission(Permission.AGENTS_RUN)
agents_manage_dependency = require_org_permission(Permission.AGENTS_MANAGE)
AgentsRunDep = Annotated[Membership, Depends(agents_run_dependency)]
AgentsManageDep = Annotated[Membership, Depends(agents_manage_dependency)]


def _get_agent(session: SessionDep, organization_id: UUID, agent_id: UUID) -> Agent:
    agent = session.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


def _get_task(session: SessionDep, organization_id: UUID, task_id: UUID) -> Task:
    task = session.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.organization_id == organization_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post(
    "/{organization_id}/agents",
    response_model=AgentPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_agent(
    organization_id: UUID,
    payload: AgentCreate,
    _membership: AgentsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Agent:
    existing = session.scalar(
        select(Agent).where(
            Agent.organization_id == organization_id,
            Agent.slug == payload.slug,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent slug already exists",
        )

    agent = Agent(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        status=AgentStatus.ACTIVE.value,
        capabilities=payload.capabilities,
        runtime_config=payload.runtime_config,
    )
    session.add(agent)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="agent.created",
        resource_type="agent",
        resource_id=str(agent.id),
        details={"slug": agent.slug, "capabilities": agent.capabilities},
    )
    session.commit()
    session.refresh(agent)
    return agent


@router.get("/{organization_id}/agents", response_model=list[AgentPublic])
def list_agents(
    organization_id: UUID,
    _membership: AgentsRunDep,
    session: SessionDep,
) -> list[Agent]:
    return list(
        session.scalars(
            select(Agent)
            .where(Agent.organization_id == organization_id)
            .order_by(Agent.name)
        )
    )


@router.post(
    "/{organization_id}/tasks",
    response_model=TaskPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    organization_id: UUID,
    payload: TaskCreate,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Task:
    assigned_agent = None
    task_status = TaskStatus.QUEUED
    if payload.assigned_agent_id is not None:
        assigned_agent = _get_agent(session, organization_id, payload.assigned_agent_id)
        if assigned_agent.status != AgentStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot assign a disabled agent",
            )
        task_status = TaskStatus.ASSIGNED

    task = Task(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        assigned_agent_id=assigned_agent.id if assigned_agent else None,
        title=payload.title,
        objective=payload.objective,
        priority=payload.priority,
        status=task_status.value,
        input_data=payload.input_data,
    )
    session.add(task)
    session.flush()
    session.add(
        TaskEvent(
            organization_id=organization_id,
            task_id=task.id,
            actor_user_id=current_user.id,
            event_type="task.created",
            details={
                "status": task.status,
                "assigned_agent_id": str(task.assigned_agent_id)
                if task.assigned_agent_id
                else None,
            },
        )
    )
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="task.created",
        resource_type="task",
        resource_id=str(task.id),
        details={"status": task.status, "priority": task.priority},
    )
    session.commit()
    session.refresh(task)
    return task


@router.get("/{organization_id}/tasks", response_model=list[TaskPublic])
def list_tasks(
    organization_id: UUID,
    _membership: AgentsRunDep,
    session: SessionDep,
) -> list[Task]:
    return list(
        session.scalars(
            select(Task)
            .where(Task.organization_id == organization_id)
            .order_by(Task.created_at.desc())
        )
    )


@router.get("/{organization_id}/tasks/{task_id}", response_model=TaskPublic)
def get_task(
    organization_id: UUID,
    task_id: UUID,
    _membership: AgentsRunDep,
    session: SessionDep,
) -> Task:
    return _get_task(session, organization_id, task_id)


@router.post("/{organization_id}/tasks/{task_id}/assign", response_model=TaskPublic)
def assign_task(
    organization_id: UUID,
    task_id: UUID,
    payload: TaskAssignRequest,
    _membership: AgentsManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Task:
    task = _get_task(session, organization_id, task_id)
    agent = _get_agent(session, organization_id, payload.agent_id)
    if agent.status != AgentStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is disabled")
    if TaskStatus(task.status) not in {TaskStatus.QUEUED, TaskStatus.ASSIGNED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only queued or assigned tasks can be assigned",
        )

    previous_agent_id = task.assigned_agent_id
    task.assigned_agent_id = agent.id
    if task.status == TaskStatus.QUEUED.value:
        transition_task(task, TaskStatus.ASSIGNED)

    session.add(
        TaskEvent(
            organization_id=organization_id,
            task_id=task.id,
            actor_user_id=current_user.id,
            event_type="task.assigned",
            details={
                "previous_agent_id": str(previous_agent_id) if previous_agent_id else None,
                "agent_id": str(agent.id),
            },
        )
    )
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="task.assigned",
        resource_type="task",
        resource_id=str(task.id),
        details={"agent_id": str(agent.id)},
    )
    session.commit()
    session.refresh(task)
    return task


@router.post("/{organization_id}/tasks/{task_id}/transition", response_model=TaskPublic)
def transition_task_state(
    organization_id: UUID,
    task_id: UUID,
    payload: TaskTransitionRequest,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Task:
    task = _get_task(session, organization_id, task_id)
    previous_status = task.status
    try:
        transition_task(
            task,
            payload.status,
            output_data=payload.output_data,
            error_message=payload.error_message,
        )
    except TaskTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    session.add(
        TaskEvent(
            organization_id=organization_id,
            task_id=task.id,
            actor_user_id=current_user.id,
            actor_agent_id=task.assigned_agent_id,
            event_type="task.status_changed",
            details={"from": previous_status, "to": task.status},
        )
    )
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="task.status_changed",
        resource_type="task",
        resource_id=str(task.id),
        details={"from": previous_status, "to": task.status},
    )
    session.commit()
    session.refresh(task)
    return task


@router.get(
    "/{organization_id}/tasks/{task_id}/events",
    response_model=list[TaskEventPublic],
)
def list_task_events(
    organization_id: UUID,
    task_id: UUID,
    _membership: AgentsRunDep,
    session: SessionDep,
) -> list[TaskEvent]:
    _get_task(session, organization_id, task_id)
    return list(
        session.scalars(
            select(TaskEvent)
            .where(
                TaskEvent.organization_id == organization_id,
                TaskEvent.task_id == task_id,
            )
            .order_by(TaskEvent.occurred_at, TaskEvent.id)
        )
    )
