from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    mission: str | None = Field(default=None, max_length=4000)
    owner_agent_id: UUID | None = None
    priority: int = Field(default=50, ge=0, le=100)
    budget_limit_usd: float = Field(default=0.0, ge=0)
    resource_limit_units: int = Field(default=100, ge=0, le=1_000_000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    mission: str | None = Field(default=None, max_length=4000)
    owner_agent_id: UUID | None = None
    status: str | None = Field(default=None, pattern=r"^(active|paused|archived)$")
    priority: int | None = Field(default=None, ge=0, le=100)
    budget_limit_usd: float | None = Field(default=None, ge=0)
    resource_limit_units: int | None = Field(default=None, ge=0, le=1_000_000)
    metadata_json: dict[str, Any] | None = None


class DepartmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    owner_agent_id: UUID | None
    name: str
    slug: str
    mission: str | None
    status: str
    priority: int
    budget_limit_usd: float
    resource_limit_units: int
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class GoalCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=8000)
    department_id: UUID | None = None
    parent_goal_id: UUID | None = None
    owner_agent_id: UUID | None = None
    status: str = Field(default="planned", pattern=r"^(planned|active|achieved|blocked|cancelled)$")
    priority: int = Field(default=50, ge=0, le=100)
    target_metric: str | None = Field(default=None, max_length=160)
    target_value: float | None = None
    current_value: float = 0.0
    due_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=8000)
    department_id: UUID | None = None
    parent_goal_id: UUID | None = None
    owner_agent_id: UUID | None = None
    status: str | None = Field(
        default=None,
        pattern=r"^(planned|active|achieved|blocked|cancelled)$",
    )
    priority: int | None = Field(default=None, ge=0, le=100)
    target_metric: str | None = Field(default=None, max_length=160)
    target_value: float | None = None
    current_value: float | None = None
    due_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class GoalPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    department_id: UUID | None
    parent_goal_id: UUID | None
    owner_agent_id: UUID | None
    created_by_user_id: UUID | None
    title: str
    description: str | None
    status: str
    priority: int
    target_metric: str | None
    target_value: float | None
    current_value: float
    due_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=8000)
    department_id: UUID | None = None
    goal_id: UUID | None = None
    lead_agent_id: UUID | None = None
    status: str = Field(
        default="planned",
        pattern=r"^(planned|active|paused|blocked|completed|cancelled)$",
    )
    priority: int = Field(default=50, ge=0, le=100)
    budget_limit_usd: float = Field(default=0.0, ge=0)
    budget_spent_usd: float = Field(default=0.0, ge=0)
    resource_limit_units: int = Field(default=100, ge=0, le=1_000_000)
    resource_used_units: int = Field(default=0, ge=0, le=1_000_000)
    start_at: datetime | None = None
    due_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    department_id: UUID | None = None
    goal_id: UUID | None = None
    lead_agent_id: UUID | None = None
    status: str | None = Field(
        default=None,
        pattern=r"^(planned|active|paused|blocked|completed|cancelled)$",
    )
    priority: int | None = Field(default=None, ge=0, le=100)
    budget_limit_usd: float | None = Field(default=None, ge=0)
    budget_spent_usd: float | None = Field(default=None, ge=0)
    resource_limit_units: int | None = Field(default=None, ge=0, le=1_000_000)
    resource_used_units: int | None = Field(default=None, ge=0, le=1_000_000)
    start_at: datetime | None = None
    due_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class ProjectResourceAllocation(BaseModel):
    budget_limit_usd: float | None = Field(default=None, ge=0)
    resource_limit_units: int | None = Field(default=None, ge=0, le=1_000_000)
    reason: str = Field(min_length=3, max_length=1000)


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    department_id: UUID | None
    goal_id: UUID | None
    lead_agent_id: UUID | None
    created_by_user_id: UUID | None
    name: str
    slug: str
    description: str | None
    status: str
    priority: int
    budget_limit_usd: float
    budget_spent_usd: float
    resource_limit_units: int
    resource_used_units: int
    start_at: datetime | None
    due_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DelegationCreate(BaseModel):
    source_department_id: UUID
    target_department_id: UUID
    title: str = Field(min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=8000)
    project_id: UUID | None = None
    goal_id: UUID | None = None
    assigned_agent_id: UUID | None = None
    priority: int = Field(default=50, ge=0, le=100)
    requested_resource_units: int = Field(default=0, ge=0, le=1_000_000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DelegationUpdate(BaseModel):
    assigned_agent_id: UUID | None = None
    status: str | None = Field(
        default=None,
        pattern=r"^(proposed|accepted|in_progress|completed|rejected|cancelled)$",
    )
    priority: int | None = Field(default=None, ge=0, le=100)
    requested_resource_units: int | None = Field(default=None, ge=0, le=1_000_000)
    metadata_json: dict[str, Any] | None = None


class DelegationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    source_department_id: UUID
    target_department_id: UUID
    project_id: UUID | None
    goal_id: UUID | None
    assigned_agent_id: UUID | None
    created_by_user_id: UUID | None
    title: str
    description: str | None
    status: str
    priority: int
    requested_resource_units: int
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
