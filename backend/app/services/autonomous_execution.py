from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.orchestration import ApprovalStatus
from backend.app.core.tasking import TaskStatus
from backend.app.core.tools import ToolRunStatus
from backend.app.models.agent import Agent
from backend.app.models.model_invocation import ModelInvocation
from backend.app.models.orchestration import (
    OrchestrationApproval,
    OrchestrationRun,
    OrchestrationStep,
)
from backend.app.models.task import Task, TaskEvent
from backend.app.models.tool_definition import ToolDefinition
from backend.app.models.tool_run import ToolRun
from backend.app.services.agent_runtime import AgentRuntimeError, execute_agent_task
from backend.app.services.audit import record_audit
from backend.app.services.model_gateway import ModelGateway
from backend.app.services.orchestrator import refresh_orchestration_status
from backend.app.services.project_delivery import sync_project_delivery_outcome
from backend.app.services.task_engine import transition_task
from backend.app.services.tool_gateway import (
    ToolGatewayError,
    approve_tool_run,
    create_tool_run,
    execute_tool_run,
)


class AutonomousExecutionError(RuntimeError):
    pass


def _runtime_budget_reservation(run: OrchestrationRun) -> float | None:
    governor = (run.context or {}).get("portfolio_governor") or {}
    reservation = governor.get("budget_reservation") or {}
    if reservation.get("status") != "active":
        return None
    try:
        return max(float(reservation.get("amount_usd", 0)), 0)
    except (TypeError, ValueError):
        return None


def _recorded_run_cost(
    session: Session,
    *,
    steps: list[OrchestrationStep],
) -> float:
    task_ids = [step.task_id for step in steps]
    if not task_ids:
        return 0.0
    invocations = session.scalars(
        select(ModelInvocation).where(ModelInvocation.task_id.in_(task_ids))
    )
    fallback = settings.project_estimated_cost_per_step_usd
    return round(
        sum(
            float(invocation.estimated_cost_usd)
            if invocation.estimated_cost_usd is not None
            else fallback
            for invocation in invocations
            if invocation.status == "succeeded"
        ),
        8,
    )


def runtime_budget_allows_next_step(
    *,
    reservation_usd: float | None,
    recorded_cost_usd: float,
    estimated_next_step_usd: float,
) -> bool:
    if reservation_usd is None:
        return True
    return recorded_cost_usd + estimated_next_step_usd <= reservation_usd + 1e-8


def _compact_output(
    output_data: Mapping[str, Any] | None,
    *,
    max_text_chars: int,
) -> dict[str, Any]:
    if not output_data:
        return {}
    compact = dict(output_data)
    text = compact.get("text")
    if isinstance(text, str) and len(text) > max_text_chars:
        compact["text"] = text[:max_text_chars] + "..."
    return compact


def _upstream_result(
    step: OrchestrationStep,
    task: Task,
    *,
    max_text_chars: int,
) -> dict[str, Any]:
    return {
        "sequence": step.sequence,
        "title": step.title,
        "task_id": str(task.id),
        "output": _compact_output(
            task.output_data,
            max_text_chars=max_text_chars,
        ),
    }


def _clone_failed_task(
    session: Session,
    *,
    step: OrchestrationStep,
    task: Task,
    actor_user_id: UUID,
) -> Task:
    if task.assigned_agent_id is None:
        raise AutonomousExecutionError("Failed task has no assigned agent to retry")

    replacement = Task(
        organization_id=task.organization_id,
        created_by_user_id=actor_user_id,
        assigned_agent_id=task.assigned_agent_id,
        title=task.title,
        objective=task.objective,
        priority=task.priority,
        status=TaskStatus.ASSIGNED.value,
        input_data={
            **(task.input_data or {}),
            "retry_of_task_id": str(task.id),
        },
    )
    session.add(replacement)
    session.flush()
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=replacement.id,
            actor_user_id=actor_user_id,
            actor_agent_id=task.assigned_agent_id,
            event_type="task.retry.created",
            details={
                "previous_task_id": str(task.id),
                "orchestration_step_id": str(step.id),
            },
        )
    )
    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="task.retry.created",
        resource_type="task",
        resource_id=str(replacement.id),
        details={
            "previous_task_id": str(task.id),
            "orchestration_step_id": str(step.id),
        },
    )
    step.task_id = replacement.id
    step.assigned_agent_id = replacement.assigned_agent_id
    session.commit()
    session.refresh(replacement)
    return replacement


def _tool_request(task: Task) -> tuple[str, dict[str, Any]] | None:
    raw = (task.input_data or {}).get("tool_request")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise AutonomousExecutionError("Tool request must be an object")
    slug = raw.get("slug")
    payload = raw.get("input", {})
    if not isinstance(slug, str) or not slug.strip():
        raise AutonomousExecutionError("Tool request requires a valid slug")
    if not isinstance(payload, dict):
        raise AutonomousExecutionError("Tool request input must be an object")
    return slug.strip(), dict(payload)


def _record_tool_task_failure(
    session: Session,
    *,
    task: Task,
    agent: Agent,
    actor_user_id: UUID,
    message: str,
    tool_slug: str | None,
) -> None:
    if TaskStatus(task.status) is TaskStatus.ASSIGNED:
        transition_task(task, TaskStatus.RUNNING)
    if TaskStatus(task.status) is TaskStatus.RUNNING:
        transition_task(task, TaskStatus.FAILED, error_message=message)
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="agent.tool.failed",
            details={"tool_slug": tool_slug, "error": message},
        )
    )
    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="agent.tool.failed",
        resource_type="task",
        resource_id=str(task.id),
        details={"agent_id": str(agent.id), "tool_slug": tool_slug, "error": message},
    )
    session.commit()


def _complete_tool_task(
    session: Session,
    *,
    task: Task,
    agent: Agent,
    tool: ToolDefinition,
    tool_run: ToolRun,
    actor_user_id: UUID,
) -> None:
    output = tool_run.output_data or {}
    provider_evidence = output.get("evidence") if isinstance(output, dict) else None
    receipt_id = (
        str(provider_evidence.get("receipt_id"))
        if isinstance(provider_evidence, dict) and provider_evidence.get("receipt_id")
        else f"tool-run:{tool_run.id}"
    )
    if TaskStatus(task.status) is TaskStatus.ASSIGNED:
        transition_task(task, TaskStatus.RUNNING)
    transition_task(
        task,
        TaskStatus.SUCCEEDED,
        output_data={
            "text": (
                f"Registered tool '{tool.slug}' executed with verified receipt "
                f"{receipt_id}."
            ),
            "execution_type": "tool",
            "provider": tool.provider,
            "tool_slug": tool.slug,
            "tool_id": str(tool.id),
            "tool_run_id": str(tool_run.id),
            "tool_output": output,
            "evidence": {
                "receipt_id": receipt_id,
                "tool_run_id": str(tool_run.id),
                "provider": tool.provider,
            },
        },
    )
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="agent.tool.completed",
            details={
                "tool_slug": tool.slug,
                "tool_run_id": str(tool_run.id),
                "receipt_id": receipt_id,
            },
        )
    )
    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="agent.tool.completed",
        resource_type="task",
        resource_id=str(task.id),
        details={
            "agent_id": str(agent.id),
            "tool_slug": tool.slug,
            "tool_run_id": str(tool_run.id),
            "receipt_id": receipt_id,
        },
    )
    session.commit()
    session.refresh(task)


def _execute_registered_tool(
    session: Session,
    *,
    task: Task,
    agent: Agent,
    actor_user_id: UUID,
    confirmed_sensitive_action: bool,
) -> tuple[str, str | None]:
    try:
        request = _tool_request(task)
    except AutonomousExecutionError as exc:
        message = str(exc)
        _record_tool_task_failure(
            session,
            task=task,
            agent=agent,
            actor_user_id=actor_user_id,
            message=message,
            tool_slug=None,
        )
        return "failed", "invalid_tool_request"
    if request is None:
        return "not_applicable", None
    tool_slug, input_data = request

    tool = session.scalar(
        select(ToolDefinition).where(
            ToolDefinition.organization_id == task.organization_id,
            ToolDefinition.slug == tool_slug,
        )
    )
    if tool is None:
        _record_tool_task_failure(
            session,
            task=task,
            agent=agent,
            actor_user_id=actor_user_id,
            message=f"Registered tool not found: {tool_slug}",
            tool_slug=tool_slug,
        )
        return "failed", "tool_not_found"
    if agent.allowed_tool_slugs is not None and tool.slug not in agent.allowed_tool_slugs:
        _record_tool_task_failure(
            session,
            task=task,
            agent=agent,
            actor_user_id=actor_user_id,
            message=f"Tool is not allowed for agent version {agent.version}",
            tool_slug=tool.slug,
        )
        return "failed", "tool_not_allowed"

    tool_run = session.scalar(
        select(ToolRun)
        .where(
            ToolRun.organization_id == task.organization_id,
            ToolRun.task_id == task.id,
            ToolRun.tool_id == tool.id,
        )
        .order_by(ToolRun.requested_at.desc())
        .limit(1)
    )
    if tool_run is None:
        try:
            tool_run = create_tool_run(
                session,
                tool=tool,
                organization_id=task.organization_id,
                requested_by_user_id=actor_user_id,
                input_data=input_data,
                task_id=task.id,
                agent_id=agent.id,
            )
        except ToolGatewayError as exc:
            _record_tool_task_failure(
                session,
                task=task,
                agent=agent,
                actor_user_id=actor_user_id,
                message=str(exc),
                tool_slug=tool.slug,
            )
            return "failed", "tool_gateway_rejected"

    if (
        tool_run.status == ToolRunStatus.PENDING_APPROVAL.value
        and confirmed_sensitive_action
    ):
        try:
            tool_run = approve_tool_run(
                session,
                run=tool_run,
                actor_user_id=actor_user_id,
            )
        except ToolGatewayError as exc:
            _record_tool_task_failure(
                session,
                task=task,
                agent=agent,
                actor_user_id=actor_user_id,
                message=str(exc),
                tool_slug=tool.slug,
            )
            return "failed", "tool_approval_failed"

    if tool_run.status == ToolRunStatus.APPROVED.value:
        try:
            tool_run = execute_tool_run(
                session,
                run=tool_run,
                tool=tool,
                actor_user_id=actor_user_id,
            )
        except ToolGatewayError as exc:
            _record_tool_task_failure(
                session,
                task=task,
                agent=agent,
                actor_user_id=actor_user_id,
                message=str(exc),
                tool_slug=tool.slug,
            )
            return "failed", "tool_execution_failed"

    if tool_run.status == ToolRunStatus.SUCCEEDED.value:
        _complete_tool_task(
            session,
            task=task,
            agent=agent,
            tool=tool,
            tool_run=tool_run,
            actor_user_id=actor_user_id,
        )
        return "succeeded", None
    if tool_run.status == ToolRunStatus.PENDING_APPROVAL.value:
        return "approval_required", "tool_approval_required"
    if tool_run.status == ToolRunStatus.RUNNING.value:
        return "blocked", "tool_run_in_progress"

    message = tool_run.error_message or f"Tool run ended with status {tool_run.status}"
    _record_tool_task_failure(
        session,
        task=task,
        agent=agent,
        actor_user_id=actor_user_id,
        message=message,
        tool_slug=tool.slug,
    )
    return "failed", f"tool_{tool_run.status}"


def execute_orchestration_autonomously(
    session: Session,
    *,
    run: OrchestrationRun,
    actor_user_id: UUID,
    stop_on_failure: bool = True,
    max_steps: int = 50,
    max_retries_per_step: int = 0,
    max_upstream_text_chars: int = 4000,
    gateway: ModelGateway | None = None,
) -> dict[str, Any]:
    if max_steps < 1:
        raise AutonomousExecutionError("max_steps must be at least 1")
    if not 0 <= max_retries_per_step <= 2:
        raise AutonomousExecutionError("max_retries_per_step must be between 0 and 2")

    steps = list(
        session.scalars(
            select(OrchestrationStep)
            .where(OrchestrationStep.orchestration_run_id == run.id)
            .order_by(OrchestrationStep.sequence)
        )
    )
    owner_command = (run.context or {}).get("owner_command") or {}
    operator_context = (run.context or {}).get("seldrune_gpt_operator") or {}
    standing_owner_authorization = (
        bool(operator_context)
        and owner_command.get("approval_status") == "approved"
    )
    confirmed_sensitive_action = (
        standing_owner_authorization and bool(operator_context.get("confirmed"))
    )

    approvals_by_step = {
        approval.orchestration_step_id: approval
        for approval in session.scalars(
            select(OrchestrationApproval).where(
                OrchestrationApproval.orchestration_run_id == run.id,
                OrchestrationApproval.organization_id == run.organization_id,
            )
        )
    }
    report: dict[str, Any] = {
        "mode": "sequential-v1",
        "executed_steps": 0,
        "skipped_succeeded_steps": 0,
        "retried_steps": 0,
        "failed_steps": 0,
        "blocked_steps": 0,
        "approval_blocked_steps": 0,
        "halted_reason": None,
        "last_sequence": None,
        "budget_reservation_usd": _runtime_budget_reservation(run),
        "recorded_cost_usd": 0.0,
        "estimated_next_step_usd": settings.project_estimated_cost_per_step_usd,
    }
    upstream: list[dict[str, Any]] = []

    record_audit(
        session,
        organization_id=run.organization_id,
        actor_user_id=actor_user_id,
        action="orchestration.autonomous.started",
        resource_type="orchestration",
        resource_id=str(run.id),
        details={
            "max_steps": max_steps,
            "max_retries_per_step": max_retries_per_step,
            "stop_on_failure": stop_on_failure,
        },
    )
    session.commit()

    processed = 0
    for step in steps:
        if processed >= max_steps:
            report["halted_reason"] = "step_limit"
            break

        task = session.get(Task, step.task_id)
        if task is None or task.organization_id != run.organization_id:
            report["blocked_steps"] += 1
            report["halted_reason"] = "missing_task"
            report["last_sequence"] = step.sequence
            break

        task_status = TaskStatus(task.status)
        if task_status is TaskStatus.SUCCEEDED:
            upstream.append(
                _upstream_result(
                    step,
                    task,
                    max_text_chars=max_upstream_text_chars,
                )
            )
            report["skipped_succeeded_steps"] += 1
            report["last_sequence"] = step.sequence
            continue

        retries_used = 0
        if task_status is TaskStatus.FAILED and max_retries_per_step > 0:
            task = _clone_failed_task(
                session,
                step=step,
                task=task,
                actor_user_id=actor_user_id,
            )
            retries_used += 1
            report["retried_steps"] += 1
            task_status = TaskStatus(task.status)

        if task_status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            report["failed_steps"] += 1
            report["last_sequence"] = step.sequence
            if stop_on_failure:
                report["halted_reason"] = f"task_{task_status.value}"
                break
            continue

        if task_status is not TaskStatus.ASSIGNED or task.assigned_agent_id is None:
            report["blocked_steps"] += 1
            report["halted_reason"] = "unmatched_or_unassigned"
            report["last_sequence"] = step.sequence
            break

        agent = session.get(Agent, task.assigned_agent_id)
        if agent is None or agent.organization_id != run.organization_id:
            report["blocked_steps"] += 1
            report["halted_reason"] = "missing_agent"
            report["last_sequence"] = step.sequence
            break

        if step.requires_approval and not standing_owner_authorization:
            approval = approvals_by_step.get(step.id)
            approval_status = approval.status if approval is not None else None
            if approval is None:
                approval_block_reason = "approval_missing"
            elif approval.status == ApprovalStatus.PENDING.value:
                approval_block_reason = "approval_required"
            elif approval.status == ApprovalStatus.REJECTED.value:
                approval_block_reason = "approval_rejected"
            elif approval.status == ApprovalStatus.APPROVED.value:
                approval_block_reason = None
            else:
                approval_block_reason = "approval_invalid"

            if approval_block_reason is not None:
                report["blocked_steps"] += 1
                report["approval_blocked_steps"] += 1
                report["halted_reason"] = approval_block_reason
                report["last_sequence"] = step.sequence
                record_audit(
                    session,
                    organization_id=run.organization_id,
                    actor_user_id=actor_user_id,
                    action="orchestration.approval.blocked",
                    resource_type="orchestration",
                    resource_id=str(run.id),
                    details={
                        "orchestration_step_id": str(step.id),
                        "sequence": step.sequence,
                        "approval_status": approval_status,
                        "halted_reason": approval_block_reason,
                    },
                )
                break

        tool_requested = (task.input_data or {}).get("tool_request") is not None
        recorded_cost = _recorded_run_cost(session, steps=steps)
        report["recorded_cost_usd"] = recorded_cost
        estimated_next_step_usd = (
            0.0 if tool_requested else report["estimated_next_step_usd"]
        )
        if not runtime_budget_allows_next_step(
            reservation_usd=report["budget_reservation_usd"],
            recorded_cost_usd=recorded_cost,
            estimated_next_step_usd=estimated_next_step_usd,
        ):
            report["blocked_steps"] += 1
            report["halted_reason"] = "budget_reservation_exceeded"
            report["last_sequence"] = step.sequence
            record_audit(
                session,
                organization_id=run.organization_id,
                actor_user_id=actor_user_id,
                action="orchestration.budget_circuit_breaker.triggered",
                resource_type="orchestration",
                resource_id=str(run.id),
                details={
                    "recorded_cost_usd": recorded_cost,
                    "estimated_next_step_usd": estimated_next_step_usd,
                    "budget_reservation_usd": report["budget_reservation_usd"],
                    "blocked_sequence": step.sequence,
                },
            )
            session.commit()
            break

        execution_context = dict(task.input_data or {})
        if standing_owner_authorization:
            execution_context["owner_authorization"] = {
                "status": "approved",
                "scope": "routine_reversible_operations",
                "approved_by": owner_command.get("approved_by") or str(actor_user_id),
                "source": "seldrune_gpt_operator",
                "instruction": (
                    "Owner authorization is already verified for this governed execution. "
                    "Do not request approval again for routine reversible work."
                ),
            }
        if upstream:
            execution_context["upstream_results"] = upstream
        if execution_context != (task.input_data or {}):
            task.input_data = execution_context
            session.add(
                TaskEvent(
                    organization_id=task.organization_id,
                    task_id=task.id,
                    actor_user_id=actor_user_id,
                    actor_agent_id=agent.id,
                    event_type="orchestration.context.attached",
                    details={
                        "orchestration_run_id": str(run.id),
                        "upstream_result_count": len(upstream),
                    },
                )
            )
            session.commit()

        tool_status, tool_reason = _execute_registered_tool(
            session,
            task=task,
            agent=agent,
            actor_user_id=actor_user_id,
            confirmed_sensitive_action=confirmed_sensitive_action,
        )
        if tool_status != "not_applicable":
            processed += 1
            report["last_sequence"] = step.sequence
            if tool_status == "succeeded":
                report["executed_steps"] += 1
                upstream.append(
                    _upstream_result(
                        step,
                        task,
                        max_text_chars=max_upstream_text_chars,
                    )
                )
                continue
            if tool_status == "approval_required":
                report["blocked_steps"] += 1
                report["approval_blocked_steps"] += 1
                report["halted_reason"] = tool_reason
                record_audit(
                    session,
                    organization_id=run.organization_id,
                    actor_user_id=actor_user_id,
                    action="orchestration.tool_approval.blocked",
                    resource_type="orchestration",
                    resource_id=str(run.id),
                    details={
                        "orchestration_step_id": str(step.id),
                        "sequence": step.sequence,
                        "halted_reason": tool_reason,
                    },
                )
                session.commit()
                break
            if tool_status == "blocked":
                report["blocked_steps"] += 1
                report["halted_reason"] = tool_reason
                break
            report["failed_steps"] += 1
            if stop_on_failure:
                report["halted_reason"] = tool_reason or "tool_execution_failed"
                break
            continue

        while True:
            processed += 1
            try:
                execute_agent_task(
                    session,
                    task=task,
                    agent=agent,
                    actor_user_id=actor_user_id,
                    gateway=gateway,
                )
                break
            except AgentRuntimeError:
                report["failed_steps"] += 1
                if retries_used >= max_retries_per_step:
                    if stop_on_failure:
                        report["halted_reason"] = "agent_runtime_failed"
                    break
                task = _clone_failed_task(
                    session,
                    step=step,
                    task=task,
                    actor_user_id=actor_user_id,
                )
                retries_used += 1
                report["retried_steps"] += 1

        report["last_sequence"] = step.sequence
        if TaskStatus(task.status) is TaskStatus.SUCCEEDED:
            report["executed_steps"] += 1
            upstream.append(
                _upstream_result(
                    step,
                    task,
                    max_text_chars=max_upstream_text_chars,
                )
            )
            continue

        if stop_on_failure:
            break

    report["recorded_cost_usd"] = _recorded_run_cost(session, steps=steps)
    refresh_orchestration_status(session, run)
    run.summary = {
        **(run.summary or {}),
        "autonomous_execution": report,
    }
    record_audit(
        session,
        organization_id=run.organization_id,
        actor_user_id=actor_user_id,
        action="orchestration.autonomous.completed",
        resource_type="orchestration",
        resource_id=str(run.id),
        details=report,
    )
    session.commit()
    session.refresh(run)
    delivery_outcome = sync_project_delivery_outcome(
        session,
        run=run,
        actor_user_id=actor_user_id,
    )
    if delivery_outcome is not None:
        run.summary = {
            **(run.summary or {}),
            "project_delivery_sync": delivery_outcome,
        }
        session.commit()
        session.refresh(run)
    return report
