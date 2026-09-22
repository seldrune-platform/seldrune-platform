from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanStepInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    capabilities: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=-100, le=100)
    requires_approval: bool = False
    tool_slug: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        max_length=100,
    )
    tool_input: dict[str, Any] = Field(default_factory=dict)


class OrchestrationCreate(BaseModel):
    objective: str = Field(min_length=5, max_length=8000)
    context: dict[str, Any] = Field(default_factory=dict)
    plan: list[PlanStepInput] | None = None


class AutonomousExecutionRequest(BaseModel):
    stop_on_failure: bool = True
    max_steps: int = Field(default=50, ge=1, le=100)
    max_retries_per_step: int = Field(default=0, ge=0, le=2)
    max_upstream_text_chars: int = Field(default=4000, ge=500, le=20000)


class AutonomousExecutionReport(BaseModel):
    mode: str
    executed_steps: int
    skipped_succeeded_steps: int
    retried_steps: int
    failed_steps: int
    blocked_steps: int
    approval_blocked_steps: int = 0
    halted_reason: str | None
    last_sequence: int | None
    budget_reservation_usd: float | None = None
    recorded_cost_usd: float = 0.0
    estimated_next_step_usd: float = 0.0


class OrchestrationStepPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    orchestration_run_id: UUID
    organization_id: UUID
    task_id: UUID
    assigned_agent_id: UUID | None
    sequence: int
    title: str
    objective: str
    required_capabilities: list[str]
    requires_approval: bool
    match_score: int
    created_at: datetime


class OrchestrationRunPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    objective: str
    status: str
    planner_version: str
    context: dict[str, Any]
    summary: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    steps: list[OrchestrationStepPublic] = Field(default_factory=list)


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    decision_note: str | None = Field(default=None, max_length=2000)


class OrchestrationApprovalPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    orchestration_run_id: UUID
    orchestration_step_id: UUID
    status: Literal["pending", "approved", "rejected"]
    requested_by_user_id: UUID | None
    decided_by_user_id: UUID | None
    decision_note: str | None
    requested_at: datetime
    decided_at: datetime | None


class AutonomousExecutionResponse(BaseModel):
    run: OrchestrationRunPublic
    execution: AutonomousExecutionReport
