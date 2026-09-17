from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.tasking import AgentStatus, TaskStatus


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
    )
    description: str | None = Field(default=None, max_length=4000)
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    runtime_config: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    capabilities: list[str] | None = Field(default=None, max_length=100)
    runtime_config: dict[str, Any] | None = None


class AgentStatusUpdate(BaseModel):
    status: AgentStatus


class AgentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str | None
    status: AgentStatus
    capabilities: list[str]
    runtime_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    objective: str = Field(min_length=2, max_length=12000)
    priority: int = Field(default=0, ge=-100, le=100)
    input_data: dict[str, Any] = Field(default_factory=dict)
    assigned_agent_id: UUID | None = None


class TaskAssignRequest(BaseModel):
    agent_id: UUID


class TaskTransitionRequest(BaseModel):
    status: TaskStatus
    output_data: dict[str, Any] | None = None
    error_message: str | None = Field(default=None, max_length=8000)


class TaskPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    assigned_agent_id: UUID | None
    title: str
    objective: str
    priority: int
    status: TaskStatus
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TaskEventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    task_id: UUID
    actor_user_id: UUID | None
    actor_agent_id: UUID | None
    event_type: str
    details: dict[str, Any]
    occurred_at: datetime
