from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.tasking import TaskStatus
from backend.app.models.agent import Agent
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task, TaskEvent
from backend.app.services.agent_runtime import AgentRuntimeError, execute_agent_task
from backend.app.services.audit import record_audit
from backend.app.services.project_delivery import sync_project_delivery_outcome
from backend.app.services.model_gateway import ModelGateway
from backend.app.services.orchestrator import refresh_orchestration_status


class AutonomousExecutionError(RuntimeError):
    pass


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
    report: dict[str, Any] = {
        "mode": "sequential-v1",
        "executed_steps": 0,
        "skipped_succeeded_steps": 0,
        "retried_steps": 0,
        "failed_steps": 0,
        "blocked_steps": 0,
        "halted_reason": None,
        "last_sequence": None,
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

        status = TaskStatus(task.status)
        if status is TaskStatus.SUCCEEDED:
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
        if status is TaskStatus.FAILED and max_retries_per_step > 0:
            task = _clone_failed_task(
                session,
                step=step,
                task=task,
                actor_user_id=actor_user_id,
            )
            retries_used += 1
            report["retried_steps"] += 1
            status = TaskStatus(task.status)

        if status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            report["failed_steps"] += 1
            report["last_sequence"] = step.sequence
            if stop_on_failure:
                report["halted_reason"] = f"task_{status.value}"
                break
            continue

        if status is not TaskStatus.ASSIGNED or task.assigned_agent_id is None:
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

        if upstream:
            task.input_data = {
                **(task.input_data or {}),
                "upstream_results": upstream,
            }
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
