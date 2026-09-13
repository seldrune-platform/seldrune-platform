from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchConnectorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    description: str | None = None
    provider: str = Field(min_length=2, max_length=40)
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchConnectorPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    name: str
    slug: str
    description: str | None
    provider: str
    status: str
    config_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ResearchSessionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    query: str = Field(min_length=2, max_length=12000)
    objective: str | None = None
    connector_ids: list[UUID] = Field(default_factory=list)


class ResearchSessionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    title: str
    query: str
    objective: str | None
    status: str
    connector_ids: list[str]
    summary: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
