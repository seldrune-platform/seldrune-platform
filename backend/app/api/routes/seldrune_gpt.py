import re
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from pydantic import BaseModel, Field

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _get_run
from backend.app.api.routes.owner_commands import (
    approve_owner_command,
    create_owner_command,
    execute_owner_command,
    get_owner_command_brief,
)
from backend.app.core.config import settings
from backend.app.core.modeling import ModelProvider, ModelRequest
from backend.app.core.rbac import Permission, Role
from backend.app.models.membership import Membership
from backend.app.models.orchestration import OrchestrationStep
from backend.app.models.seldrune_gpt_message import SeldruneGPTMessage
from backend.app.models.task import Task
from backend.app.models.tool_definition import ToolDefinition
from backend.app.schemas.orchestration import AutonomousExecutionRequest, OrchestrationCreate
from backend.app.services.audit import record_audit
from backend.app.services.external_actions import default_external_action_catalog
from backend.app.services.model_gateway import ModelGateway, ModelGatewayError
from backend.app.services.tool_bootstrap import (
    configured_external_tool_status,
    ensure_configured_external_tools,
)

router = APIRouter(prefix="/organizations", tags=["seldrune-gpt"])
run_dependency = require_org_permission(Permission.AGENTS_RUN)
AgentsRunDep = Annotated[Membership, Depends(run_dependency)]
OwnerOperatorDep = Annotated[
    Membership,
    Depends(require_org_permission(Permission.ORG_MANAGE)),
]


_OPERATOR_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "destructive_change",
        re.compile(r"\b(delete|erase|wipe|drop|destroy)\b", re.I),
    ),
    (
        "financial_commitment",
        re.compile(
            r"\b(pay|purchase|buy|subscribe|spend|transfer|refund|invoice)\b",
            re.I,
        ),
    ),
    (
        "credential_or_access_change",
        re.compile(
            r"\b(password|credential|secret|api[ -]?key|token|mfa|permission|access)\b",
            re.I,
        ),
    ),
    (
        "legal_or_people_commitment",
        re.compile(
            r"\b(sign|contract|hire|fire|terminate employment|legal filing)\b",
            re.I,
        ),
    ),
    (
        "repository_merge",
        re.compile(
            r"\bmerge\b.{0,80}\b(pull request|pr)\b"
            r"|\b(pull request|pr)\b.{0,80}\bmerge\b",
            re.I,
        ),
    ),
)


def _operator_risk_reasons(order: str) -> list[str]:
    return [name for name, pattern in _OPERATOR_RISK_PATTERNS if pattern.search(order)]


_TOOL_INTENT_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "gmail",
        "send-message",
        re.compile(
            r"\b(send|notify|email|mail)\b.{0,80}"
            r"\b(email|mail|gmail|owner|recipient|client|customer|team)\b",
            re.I,
        ),
    ),
    (
        "github",
        "create-issue",
        re.compile(
            r"\b(create|open|file)\b.{0,80}\b(issue|bug)\b",
            re.I,
        ),
    ),
    (
        "github",
        "comment",
        re.compile(
            r"\b(comment|reply)\b.{0,80}\b(issue|pull request|pr)\b",
            re.I,
        ),
    ),
    (
        "github",
        "create-pull-request",
        re.compile(
            r"\b(create|open)\b.{0,80}\b(pull request|pr)\b",
            re.I,
        ),
    ),
    (
        "github",
        "merge-pull-request",
        re.compile(
            r"\bmerge\b.{0,80}\b(pull request|pr)\b"
            r"|\b(pull request|pr)\b.{0,80}\bmerge\b",
            re.I,
        ),
    ),
    (
        "github",
        "dispatch-workflow",
        re.compile(
            r"\b(dispatch|trigger|run)\b.{0,80}\b(workflow|github action)\b",
            re.I,
        ),
    ),
)


def _required_external_tool_actions(order: str) -> list[tuple[str, str]]:
    required = {
        (provider, action_name)
        for provider, action_name, pattern in _TOOL_INTENT_PATTERNS
        if pattern.search(order)
    }
    deploy_requested = re.search(r"\b(deploy|redeploy)\b", order, re.I)
    github_workflow = re.search(r"\b(workflow|github action)\b", order, re.I)
    if deploy_requested and not github_workflow:
        required.add(("render", "deploy-service"))
    return sorted(required)


def _missing_external_tools(
    session: SessionDep,
    *,
    organization_id: UUID,
    order: str,
) -> tuple[list[str], list[str]]:
    required = _required_external_tool_actions(order)
    if not required:
        return [], []

    active = {
        (tool.provider, tool.action_name)
        for tool in session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == "active",
            )
        )
    }
    missing = [item for item in required if item not in active]
    if not missing:
        return [], []

    catalog = {
        (str(item["provider"]), str(item["action_name"])): item
        for item in default_external_action_catalog()
    }
    missing_tools = [f"{provider}:{action_name}" for provider, action_name in missing]
    env_locators = sorted(
        {
            str(catalog[item]["credential_env_locator"])
            for item in missing
            if item in catalog
        }
    )
    return missing_tools, env_locators


def _planned_external_tool_actions(
    session: SessionDep,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> set[tuple[str, str]]:
    tool_slugs: set[str] = set()
    tasks = session.scalars(
        select(Task)
        .join(OrchestrationStep, OrchestrationStep.task_id == Task.id)
        .where(
            OrchestrationStep.orchestration_run_id == run_id,
            Task.organization_id == organization_id,
        )
    )
    for task in tasks:
        request = (task.input_data or {}).get("tool_request")
        if isinstance(request, dict):
            slug = request.get("slug")
            if isinstance(slug, str) and slug:
                tool_slugs.add(slug)
    if not tool_slugs:
        return set()
    return {
        (tool.provider, tool.action_name)
        for tool in session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.slug.in_(tool_slugs),
            )
        )
    }


def _require_owner_role(membership: Membership) -> None:
    if membership.role != Role.OWNER.value:
        raise HTTPException(status_code=403, detail="Owner role required")


class SeldruneGPTRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)


class SeldruneGPTOperatorRequest(BaseModel):
    order: str = Field(min_length=5, max_length=8000)
    command_id: UUID | None = None
    confirm_sensitive_action: bool = False
    stop_on_failure: bool = True
    max_steps: int = Field(default=50, ge=1, le=100)
    max_retries_per_step: int = Field(default=1, ge=0, le=2)


class SeldruneGPTOperatorResponse(BaseModel):
    status: Literal[
        "completed",
        "partial",
        "approval_required",
        "configuration_required",
        "failed",
    ]
    command_id: UUID | None = None
    objective: str
    approval_required: bool
    risk_reasons: list[str]
    run_status: str
    executed_steps: int = 0
    failed_steps: int = 0
    blocked_steps: int = 0
    halted_reason: str | None = None
    evidence_url: str | None = None
    missing_tools: list[str] = Field(default_factory=list)
    configuration_hints: list[str] = Field(default_factory=list)
    brief: dict | None = None


class SeldruneGPTCapabilitiesResponse(BaseModel):
    mode: str
    execution: str
    supported_controls: list[str]
    approval_required_for: list[str]
    evidence: str
    registered_tools: list[str] = Field(default_factory=list)
    provider_readiness: dict[str, bool] = Field(default_factory=dict)
    configuration_hints: list[str] = Field(default_factory=list)


class SeldruneGPTHistoryMessage(BaseModel):
    role: str
    content: str
    model: str | None = None


class SeldruneGPTResponse(BaseModel):
    model: str
    response: str
    response_id: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider: str


@router.post("/{organization_id}/gpt", response_model=SeldruneGPTResponse)
def seldrune_gpt(
    organization_id: UUID,
    payload: SeldruneGPTRequest,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> SeldruneGPTResponse:
    if settings.model_provider != "openai":
        raise HTTPException(status_code=503, detail="OpenAI model provider is not enabled")
    history = list(
        session.scalars(
            select(SeldruneGPTMessage)
            .where(
                SeldruneGPTMessage.organization_id == organization_id,
                SeldruneGPTMessage.user_id == current_user.id,
            )
            .order_by(SeldruneGPTMessage.created_at.desc())
            .limit(12)
        )
    )
    history.reverse()
    context_lines = [f"{item.role}: {item.content}" for item in history]
    while sum(len(line) for line in context_lines) > 24000 and context_lines:
        context_lines.pop(0)
    context = "\\n".join(context_lines)
    input_text = payload.message
    if context:
        input_text = f"Recent conversation:\\n{context}\\n\\nUser: {payload.message}"
    ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    session.commit()
    active_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == "active",
            )
        )
    )
    bootstrap = configured_external_tool_status(
        session,
        organization_id=organization_id,
    )
    registered_tool_slugs = sorted(tool.slug for tool in active_tools)
    missing_provider_env = sorted(
        {
            provider["credential_env_locator"]
            for provider in bootstrap["providers"]
            if not provider["secret_available"]
        }
    )
    tool_runtime_context = (
        "Registered executable tool slugs: "
        + (", ".join(registered_tool_slugs) if registered_tool_slugs else "none")
        + ". Missing provider configuration: "
        + (", ".join(missing_provider_env) if missing_provider_env else "none")
        + "."
    )
    request = ModelRequest(
        provider=ModelProvider.OPENAI,
        model=settings.model_default,
        input_text=input_text,
        instructions=(
            "You are Seldrune GPT, the reasoning interface inside the Seldrune STI "
            "owner console. Help the owner analyze, design, and plan work. Do not claim "
            f"The configured model identifier is {settings.model_default}. "
            "When asked which model Seldrune is using, report that configured identifier exactly. "
            "Seldrune STI is an AI-native governed virtual organization: it plans work, "
            "coordinates agents and tools, records evidence, and preserves owner-controlled "
            "approvals. When the owner asks you to perform work, explain that Execute order "
            "can run the instruction through Seldrune's governed operator. Never imply that "
            "chat text alone performed an action. Do not claim an external action occurred "
            "unless Seldrune provides verified evidence. "
            + tool_runtime_context
        ),
        max_output_tokens=settings.model_max_output_tokens,
    )
    try:
        result, _latency_ms = ModelGateway(settings).generate(request)
    except ModelGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="user",
            content=payload.message,
        )
    )
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="assistant",
            content=result.output_text,
            model=result.model,
            response_id=result.response_id,
        )
    )
    session.commit()
    return SeldruneGPTResponse(
        model=result.model,
        response=result.output_text,
        response_id=result.response_id,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        latency_ms=int(_latency_ms),
        provider=settings.model_provider,
    )


@router.get(
    "/{organization_id}/gpt/capabilities",
    response_model=SeldruneGPTCapabilitiesResponse,
)
def seldrune_gpt_capabilities(
    organization_id: UUID,
    membership: OwnerOperatorDep,
    session: SessionDep,
) -> SeldruneGPTCapabilitiesResponse:
    _require_owner_role(membership)
    tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == "active",
            )
        )
    )
    readiness = configured_external_tool_status(
        session,
        organization_id=organization_id,
    )
    provider_readiness = {
        provider["provider"]: bool(provider["ready"])
        for provider in readiness["providers"]
    }
    configuration_hints = sorted(
        {
            provider["credential_env_locator"]
            for provider in readiness["providers"]
            if not provider["secret_available"]
        }
    )
    return SeldruneGPTCapabilitiesResponse(
        mode="governed-owner-operator",
        execution=(
            "single-order plan, execute, verify; fresh confirmation for "
            "high-impact commitments"
        ),
        supported_controls=[
            "organization analysis and planning",
            "research and evidence preparation",
            "agent orchestration",
            "tool execution through registered grants",
            "project delivery and recovery",
            "audited command promotion",
        ],
        approval_required_for=[name for name, _pattern in _OPERATOR_RISK_PATTERNS],
        evidence="Every order receives a durable command id, execution report, and audit trail.",
        registered_tools=sorted(tool.slug for tool in tools),
        provider_readiness=provider_readiness,
        configuration_hints=configuration_hints,
    )


@router.post(
    "/{organization_id}/gpt/operate",
    response_model=SeldruneGPTOperatorResponse,
)
def operate_seldrune_gpt(
    organization_id: UUID,
    payload: SeldruneGPTOperatorRequest,
    membership: OwnerOperatorDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> SeldruneGPTOperatorResponse:
    _require_owner_role(membership)
    ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    missing_tools, configuration_hints = _missing_external_tools(
        session,
        organization_id=organization_id,
        order=payload.order,
    )
    if missing_tools:
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="seldrune_gpt.operator_configuration_required",
            resource_type="organization",
            resource_id=str(organization_id),
            details={
                "missing_tools": missing_tools,
                "configuration_hints": configuration_hints,
            },
        )
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="assistant",
                content=(
                    "Operator configuration required. Missing executable tools: "
                    + ", ".join(missing_tools)
                    + (
                        ". Configure: " + ", ".join(configuration_hints)
                        if configuration_hints
                        else ""
                    )
                ),
                model=settings.model_default,
            )
        )
        session.commit()
        return SeldruneGPTOperatorResponse(
            status="configuration_required",
            command_id=None,
            objective=payload.order,
            approval_required=False,
            risk_reasons=[],
            run_status="not_started",
            halted_reason="required_external_tool_unavailable",
            missing_tools=missing_tools,
            configuration_hints=configuration_hints,
        )

    risk_reasons = _operator_risk_reasons(payload.order)

    if payload.command_id is None:
        created = create_owner_command(
            organization_id,
            OrchestrationCreate(
                objective=payload.order,
                context={
                    "source": "seldrune_gpt_operator",
                    "seldrune_gpt_operator": {
                        "requested_by": str(current_user.id),
                        "risk_reasons": risk_reasons,
                        "confirmation_required": bool(risk_reasons),
                    },
                },
            ),
            membership,
            current_user,
            session,
        )
        run_id = created.id
    else:
        run = _get_run(session, organization_id, payload.command_id)
        operator_context = (run.context or {}).get("seldrune_gpt_operator")
        if not operator_context:
            raise HTTPException(status_code=404, detail="Seldrune GPT operator command not found")
        if run.objective != payload.order:
            raise HTTPException(status_code=409, detail="Order does not match the pending command")
        run_id = run.id

    required_actions = set(_required_external_tool_actions(payload.order))
    planned_actions = _planned_external_tool_actions(
        session,
        organization_id=organization_id,
        run_id=run_id,
    )
    missing_planned = sorted(required_actions - planned_actions)
    evidence_url = (
        f"/api/v1/organizations/{organization_id}/owner-commands/{run_id}/brief"
    )
    if missing_planned:
        missing_planned_tools = [
            f"{provider}:{action_name}"
            for provider, action_name in missing_planned
        ]
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="seldrune_gpt.operator_required_tool_not_planned",
            resource_type="orchestration",
            resource_id=str(run_id),
            details={"missing_tools": missing_planned_tools},
        )
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="assistant",
                content=(
                    "Operator stopped before execution because the plan did not include "
                    "required external tools: "
                    + ", ".join(missing_planned_tools)
                ),
                model=settings.model_default,
            )
        )
        session.commit()
        run = _get_run(session, organization_id, run_id)
        return SeldruneGPTOperatorResponse(
            status="failed",
            command_id=run_id,
            objective=payload.order,
            approval_required=False,
            risk_reasons=risk_reasons,
            run_status=run.status,
            halted_reason="required_external_tool_not_planned",
            evidence_url=evidence_url,
            missing_tools=missing_planned_tools,
        )
    if risk_reasons and not payload.confirm_sensitive_action:
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="seldrune_gpt.operator_approval_required",
            resource_type="orchestration",
            resource_id=str(run_id),
            details={"risk_reasons": risk_reasons},
        )
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="assistant",
                content=(
                    "Operator command created. Explicit owner confirmation is required for: "
                    + ", ".join(risk_reasons)
                ),
                model=settings.model_default,
            )
        )
        session.commit()
        run = _get_run(session, organization_id, run_id)
        return SeldruneGPTOperatorResponse(
            status="approval_required",
            command_id=run_id,
            objective=payload.order,
            approval_required=True,
            risk_reasons=risk_reasons,
            run_status=run.status,
            evidence_url=evidence_url,
        )

    if risk_reasons and payload.confirm_sensitive_action:
        confirmed_run = _get_run(session, organization_id, run_id)
        operator_context = (confirmed_run.context or {}).get("seldrune_gpt_operator") or {}
        confirmed_run.context = {
            **(confirmed_run.context or {}),
            "seldrune_gpt_operator": {
                **operator_context,
                "confirmed": True,
                "confirmed_by": str(current_user.id),
            },
        }
        session.commit()

    approve_owner_command(
        organization_id,
        run_id,
        membership,
        current_user,
        session,
    )
    result = execute_owner_command(
        organization_id,
        run_id,
        AutonomousExecutionRequest(
            stop_on_failure=payload.stop_on_failure,
            max_steps=payload.max_steps,
            max_retries_per_step=payload.max_retries_per_step,
        ),
        membership,
        current_user,
        session,
    )
    report = result.execution
    brief = get_owner_command_brief(
        organization_id,
        run_id,
        membership,
        session,
    )
    if report.failed_steps:
        status_value = "failed"
    elif report.blocked_steps or report.approval_blocked_steps or report.halted_reason:
        status_value = "partial"
    else:
        status_value = "completed"
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action=f"seldrune_gpt.operator_{status_value}",
        resource_type="orchestration",
        resource_id=str(run_id),
        details={
            "risk_reasons": risk_reasons,
            "executed_steps": report.executed_steps,
            "failed_steps": report.failed_steps,
            "blocked_steps": report.blocked_steps,
            "halted_reason": report.halted_reason,
        },
    )
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="assistant",
            content=(
                f"Operator {status_value}: {report.executed_steps} steps executed, "
                f"{report.failed_steps} failed, {report.blocked_steps} blocked. "
                f"Command evidence: {run_id}."
            ),
            model=settings.model_default,
        )
    )
    session.commit()
    return SeldruneGPTOperatorResponse(
        status=status_value,
        command_id=run_id,
        objective=payload.order,
        approval_required=False,
        risk_reasons=risk_reasons,
        run_status=result.run.status,
        executed_steps=report.executed_steps,
        failed_steps=report.failed_steps,
        blocked_steps=report.blocked_steps + report.approval_blocked_steps,
        halted_reason=report.halted_reason,
        evidence_url=evidence_url,
        brief=brief,
    )


@router.get("/{organization_id}/gpt/history", response_model=list[SeldruneGPTHistoryMessage])
def seldrune_gpt_history(
    organization_id: UUID,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[SeldruneGPTHistoryMessage]:
    messages = list(
        session.scalars(
            select(SeldruneGPTMessage)
            .where(
                SeldruneGPTMessage.organization_id == organization_id,
                SeldruneGPTMessage.user_id == current_user.id,
            )
            .order_by(SeldruneGPTMessage.created_at.asc())
            .limit(100)
        )
    )
    return [
        SeldruneGPTHistoryMessage(role=item.role, content=item.content, model=item.model)
        for item in messages
    ]


@router.delete("/{organization_id}/gpt/history", status_code=204)
def clear_seldrune_gpt_history(
    organization_id: UUID,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> None:
    session.execute(
        delete(SeldruneGPTMessage).where(
            SeldruneGPTMessage.organization_id == organization_id,
            SeldruneGPTMessage.user_id == current_user.id,
        )
    )
    session.commit()
