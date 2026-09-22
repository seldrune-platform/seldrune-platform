from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinitionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    provider: str = Field(default="internal", pattern=r"^[a-z0-9][a-z0-9_-]{1,39}$")
    action_name: str = Field(min_length=2, max_length=100)
    credential_reference_id: UUID | None = None
    risk_level: str = Field(default="low", pattern=r"^(low|medium|high)$")
    approval_mode: str = Field(default="never", pattern=r"^(never|always)$")
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolDefinitionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    name: str
    slug: str
    description: str | None
    provider: str
    action_name: str
    credential_reference_id: UUID | None
    status: str
    risk_level: str
    approval_mode: str
    input_schema: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ToolRunCreate(BaseModel):
    tool_id: UUID
    task_id: UUID | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)


class ToolRunDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ToolRunPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    tool_id: UUID
    task_id: UUID | None
    agent_id: UUID | None
    requested_by_user_id: UUID | None
    decided_by_user_id: UUID | None
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    error_message: str | None
    requested_at: datetime
    decided_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
