import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.modeling import (
    InvocationStatus,
    ModelGatewayError,
    ModelProvider,
    ModelRequest,
)
from backend.app.core.tasking import AgentStatus, TaskStatus
from backend.app.models.agent import Agent
from backend.app.models.model_invocation import ModelInvocation
from backend.app.models.task import Task, TaskEvent
from backend.app.services.ai_cost_governor import apply_budget_pressure, choose_cost_route
from backend.app.services.ai_spend_guard import (
    AISpendBudgetExceeded,
    ai_spend_budget_status,
    enforce_ai_spend_budget,
)
from backend.app.services.audit import record_audit
from backend.app.services.knowledge import build_agent_context, remember_task_result
from backend.app.services.model_gateway import ModelGateway
from backend.app.services.task_engine import transition_task


class AgentRuntimeError(RuntimeError):
    pass


class AgentPolicyError(AgentRuntimeError):
    pass


def _resolve_provider(agent: Agent) -> ModelProvider:
    value = str(agent.runtime_config.get("provider", settings.model_provider)).lower()
    try:
        provider = ModelProvider(value)
    except ValueError as exc:
        raise AgentRuntimeError(f"Unsupported model provider: {value}") from exc
    if (
        agent.allowed_model_providers is not None
        and provider.value not in agent.allowed_model_providers
    ):
        raise AgentPolicyError(
            f"Model provider '{provider.value}' is not allowed for agent version {agent.version}"
        )
    return provider


def _resolve_model(agent: Agent) -> str:
    model = str(agent.runtime_config.get("model", settings.model_default)).strip()
    if agent.allowed_models is not None and model not in agent.allowed_models:
        raise AgentPolicyError(
            f"Model '{model}' is not allowed for agent version {agent.version}"
        )
    return model


def _build_instructions(agent: Agent) -> str:
    custom = agent.runtime_config.get("instructions")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    capabilities = ", ".join(agent.capabilities) or "general execution"
    return (
        f"You are {agent.name}, an Agentic AI operating inside Seldrune. "
        f"Your capabilities are: {capabilities}. Complete the assigned objective clearly, "
        "state assumptions, and return an actionable result."
    )


def _compiled_response_schema(task: Task) -> dict[str, object] | None:
    contract = (task.input_data or {}).get("compiled_execution_contract")
    if not isinstance(contract, dict):
        return None
    model_step = next(
        (
            step
            for step in contract.get("steps") or []
            if isinstance(step, dict) and step.get("kind") == "model"
        ),
        None,
    )
    response_schema = (
        model_step.get("response_schema")
        if isinstance(model_step, dict)
        else None
    )
    return response_schema if isinstance(response_schema, dict) else None


def _build_input(task: Task, knowledge_context: str = "") -> str:
    payload = json.dumps(task.input_data, sort_keys=True, default=str)
    base = f"Task: {task.title}\nObjective: {task.objective}\nContext: {payload}"

    response_schema = _compiled_response_schema(task)
    if response_schema is not None:
        schema_text = json.dumps(response_schema, sort_keys=True)
        base += (
            "\n\nCompiled execution contract requirement: return only valid JSON "
            "matching this response schema. Do not wrap the JSON in markdown fences. "
            "This model output is an execution input, not completion evidence. "
            f"Schema: {schema_text}"
        )

    if knowledge_context:
        return f"{base}\n\n{knowledge_context}"
    return base


def _estimate_cost(agent: Agent, input_tokens: int, output_tokens: int) -> float | None:
    input_rate = agent.runtime_config.get("input_cost_per_million")
    output_rate = agent.runtime_config.get("output_cost_per_million")
    if input_rate is None or output_rate is None:
        return None
    try:
        return round(
            (input_tokens / 1_000_000) * float(input_rate)
            + (output_tokens / 1_000_000) * float(output_rate),
            8,
        )
    except (TypeError, ValueError):
        return None


def execute_agent_task(
    session: Session,
    *,
    task: Task,
    agent: Agent,
    actor_user_id: UUID,
    gateway: ModelGateway | None = None,
) -> Task:
    if agent.status != AgentStatus.ACTIVE.value:
        raise AgentRuntimeError("Assigned agent is disabled")
    if task.assigned_agent_id != agent.id:
        raise AgentRuntimeError("Task is not assigned to this agent")
    if TaskStatus(task.status) is not TaskStatus.ASSIGNED:
        raise AgentRuntimeError("Only assigned tasks can be executed")

    provider = _resolve_provider(agent)
    explicit_model = (
        _resolve_model(agent)
        if isinstance(agent.runtime_config.get("model"), str)
        and str(agent.runtime_config.get("model")).strip()
        else None
    )
    spend_status = ai_spend_budget_status(
        session,
        organization_id=task.organization_id,
        settings=settings,
    )
    route = apply_budget_pressure(
        settings,
        choose_cost_route(
            settings,
            purpose="agent",
            text=task.objective,
            capabilities=agent.capabilities,
            explicit_model=explicit_model,
        ),
        monthly_utilization=float(spend_status["monthly_utilization"]),
    )
    model = route.model
    if agent.allowed_models is not None and model not in agent.allowed_models:
        permitted = [
            candidate
            for candidate in (
                settings.model_economy,
                settings.model_balanced,
                settings.model_premium,
                settings.model_default,
            )
            if candidate in agent.allowed_models
        ]
        if not permitted:
            raise AgentPolicyError(
                "No cost-governed model is allowed for this agent version"
            )
        model = permitted[0]
        route = apply_budget_pressure(
            settings,
            choose_cost_route(
                settings,
                purpose="agent",
                text=task.objective,
                capabilities=agent.capabilities,
                explicit_model=model,
            ),
            monthly_utilization=float(spend_status["monthly_utilization"]),
        )
    configured_max_output = int(
        agent.runtime_config.get("max_output_tokens", settings.model_max_output_tokens)
    )
    max_output_tokens = min(configured_max_output, route.max_output_tokens)
    try:
        enforce_ai_spend_budget(
            session,
            organization_id=task.organization_id,
            settings=settings,
            projected_usd=route.request_budget_usd,
        )
    except AISpendBudgetExceeded as exc:
        raise AgentRuntimeError(str(exc)) from exc
    knowledge_context, context_refs = build_agent_context(
        session,
        task=task,
        agent_id=agent.id,
        limit=settings.knowledge_retrieval_limit,
        max_chars=settings.knowledge_context_max_chars,
    )
    invocation = ModelInvocation(
        organization_id=task.organization_id,
        task_id=task.id,
        agent_id=agent.id,
        provider=provider.value,
        model=model,
        status=InvocationStatus.RUNNING.value,
    )
    session.add(invocation)
    transition_task(task, TaskStatus.RUNNING)
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="agent.runtime.started",
            details={
                "provider": provider.value,
                "model": model,
                "agent_version": agent.version,
                "context_refs": context_refs,
            },
        )
    )
    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="agent.runtime.started",
        resource_type="task",
        resource_id=str(task.id),
        details={
            "agent_id": str(agent.id),
            "agent_version": agent.version,
            "provider": provider.value,
            "model": model,
            "context_refs": context_refs,
        },
    )
    session.commit()

    model_gateway = gateway or ModelGateway(settings)
    request = ModelRequest(
        provider=provider,
        model=model,
        instructions=_build_instructions(agent),
        input_text=_build_input(task, knowledge_context),
        max_output_tokens=max_output_tokens,
        metadata={
            "task_id": str(task.id),
            "agent_id": str(agent.id),
            "agent_version": agent.version,
            "cost_tier": route.tier,
        },
        response_schema=_compiled_response_schema(task),
        reasoning_effort=route.reasoning_effort,
        prompt_cache_key=f"seldrune:{task.organization_id}:agent:{agent.id}",
        max_estimated_cost_usd=route.request_budget_usd,
        exact_token_preflight=False,
    )

    try:
        result, latency_ms = model_gateway.generate(request)
    except ModelGatewayError as exc:
        message = str(exc)
        invocation.status = InvocationStatus.FAILED.value
        invocation.error_message = message
        invocation.completed_at = datetime.now(UTC)
        transition_task(task, TaskStatus.FAILED, error_message=message)
        session.add(
            TaskEvent(
                organization_id=task.organization_id,
                task_id=task.id,
                actor_user_id=actor_user_id,
                actor_agent_id=agent.id,
                event_type="agent.runtime.failed",
                details={
                    "provider": provider.value,
                    "model": model,
                    "agent_version": agent.version,
                    "error": message,
                },
            )
        )
        record_audit(
            session,
            organization_id=task.organization_id,
            actor_user_id=actor_user_id,
            action="agent.runtime.failed",
            resource_type="task",
            resource_id=str(task.id),
            details={
                "agent_id": str(agent.id),
                "agent_version": agent.version,
                "error": message,
            },
        )
        session.commit()
        raise AgentRuntimeError(message) from exc

    invocation.status = InvocationStatus.SUCCEEDED.value
    invocation.provider_response_id = result.response_id
    invocation.input_tokens = result.usage.input_tokens
    invocation.output_tokens = result.usage.output_tokens
    invocation.total_tokens = result.usage.total_tokens
    invocation.estimated_cost_usd = (
        result.usage.estimated_cost_usd
        if result.usage.estimated_cost_usd is not None
        else _estimate_cost(
            agent,
            result.usage.input_tokens,
            result.usage.output_tokens,
        )
    )
    invocation.latency_ms = latency_ms
    invocation.completed_at = datetime.now(UTC)
    transition_task(
        task,
        TaskStatus.SUCCEEDED,
        output_data={
            "text": result.output_text,
            "provider": result.provider.value,
            "model": result.model,
            "response_id": result.response_id,
            "agent_version": agent.version,
            "context_refs": context_refs,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "total_tokens": result.usage.total_tokens,
                "cached_input_tokens": result.usage.cached_input_tokens,
                "estimated_cost_usd": result.usage.estimated_cost_usd,
                "cost_tier": route.tier,
            },
        },
    )
    remember_task_result(
        session,
        task=task,
        agent_id=agent.id,
        created_by_user_id=actor_user_id,
        result_text=result.output_text,
        context_refs=context_refs,
    )
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="agent.runtime.completed",
            details={
                "provider": result.provider.value,
                "model": result.model,
                "agent_version": agent.version,
                "total_tokens": result.usage.total_tokens,
                "context_refs": context_refs,
            },
        )
    )
    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="agent.runtime.completed",
        resource_type="task",
        resource_id=str(task.id),
        details={
            "agent_id": str(agent.id),
            "agent_version": agent.version,
            "provider": result.provider.value,
            "model": result.model,
            "total_tokens": result.usage.total_tokens,
            "context_refs": context_refs,
        },
    )
    session.commit()
    session.refresh(task)
    return task
