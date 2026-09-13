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


class ResearchSourceIngest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    uri: str | None = None
    content: str = Field(min_length=1, max_length=100000)
    provider: str = Field(default="manual", max_length=40)
    source_type: str = Field(default="external", max_length=40)
    connector_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchSourcePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    research_session_id: UUID
    connector_id: UUID | None
    knowledge_entry_id: UUID | None
    title: str
    uri: str | None
    provider: str
    source_type: str
    status: str
    content_sha256: str
    metadata_json: dict[str, Any]
    retrieved_at: datetime | None
    created_at: datetime


class ResearchExecuteRequest(BaseModel):
    connector_ids: list[UUID] | None = None
    max_results_per_connector: int = Field(default=10, ge=1, le=50)


class ResearchExecutionResponse(BaseModel):
    session: ResearchSessionPublic
    sources: list[ResearchSourcePublic]
