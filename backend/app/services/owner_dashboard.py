from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.agent import Agent
from backend.app.models.model_invocation import ModelInvocation
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task
from backend.app.services.outcome_verification import assess_command_outcome


def _commands(session: Session, organization_id: UUID) -> list[OrchestrationRun]:
    runs = list(
        session.scalars(
            select(OrchestrationRun)
            .where(OrchestrationRun.organization_id == organization_id)
            .order_by(OrchestrationRun.created_at.desc())
        )
    )
    return [run for run in runs if (run.context or {}).get("owner_command")]


def build_owner_dashboard(session: Session, organization_id: UUID) -> dict[str, Any]:
    commands = _commands(session, organization_id)
    run_ids = [run.id for run in commands]
    steps = (
        list(
            session.scalars(
                select(OrchestrationStep).where(
                    OrchestrationStep.orchestration_run_id.in_(run_ids)
                )
            )
        )
        if run_ids
        else []
    )
    tasks = [task for step in steps if (task := session.get(Task, step.task_id)) is not None]
    task_ids = [task.id for task in tasks]
    invocations = (
        list(
            session.scalars(
                select(ModelInvocation).where(ModelInvocation.task_id.in_(task_ids))
            )
        )
        if task_ids
        else []
    )
    approvals = [run.context["owner_command"].get("approval_status") for run in commands]
    status_counts: dict[str, int] = {}
    for run in commands:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
    return {
        "command_counts": {
            "total": len(commands),
            "awaiting_approval": approvals.count("awaiting_approval"),
            "approved": approvals.count("approved"),
            "by_status": status_counts,
        },
        "execution": {
            "total_steps": len(steps),
            "matched_steps": sum(step.assigned_agent_id is not None for step in steps),
            "succeeded_steps": sum(task.status == "succeeded" for task in tasks),
            "failed_steps": sum(task.status == "failed" for task in tasks),
        },
        "usage": {
            "model_invocations": len(invocations),
            "total_tokens": sum(item.total_tokens for item in invocations),
            "estimated_cost_usd": round(
                sum(item.estimated_cost_usd or 0 for item in invocations), 6
            ),
        },
        "recent_commands": [
            {
                "id": str(run.id),
                "objective": run.objective,
                "status": run.status,
                "approval_status": run.context["owner_command"].get("approval_status"),
                "created_at": run.created_at,
            }
            for run in commands[:10]
        ],
    }


def _duration_ms(task: Task | None) -> int | None:
    if task is None or task.started_at is None or task.completed_at is None:
        return None
    return max(0, round((task.completed_at - task.started_at).total_seconds() * 1000))


def _latest_invocations(
    session: Session, task_ids: list[UUID]
) -> dict[UUID, ModelInvocation]:
    if not task_ids:
        return {}
    items = list(
        session.scalars(
            select(ModelInvocation)
            .where(ModelInvocation.task_id.in_(task_ids))
            .order_by(ModelInvocation.created_at.desc())
        )
    )
    latest: dict[UUID, ModelInvocation] = {}
    for item in items:
        latest.setdefault(item.task_id, item)
    return latest


def build_decision_brief(session: Session, run: OrchestrationRun) -> dict[str, Any]:
    steps = list(
        session.scalars(
            select(OrchestrationStep)
            .where(OrchestrationStep.orchestration_run_id == run.id)
            .order_by(OrchestrationStep.sequence)
        )
    )
    task_by_id = {
        step.task_id: task
        for step in steps
        if (task := session.get(Task, step.task_id)) is not None
    }
    invocation_by_task = _latest_invocations(session, list(task_by_id))
    agent_ids = {step.assigned_agent_id for step in steps if step.assigned_agent_id}
    agents = {
        agent.id: agent
        for agent_id in agent_ids
        if (agent := session.get(Agent, agent_id)) is not None
    }

    details: list[dict[str, Any]] = []
    risks: list[str] = []
    total_tokens = 0
    total_cost = 0.0
    total_duration_ms = 0
    for step in steps:
        task = task_by_id.get(step.task_id)
        invocation = invocation_by_task.get(step.task_id)
        task_status = task.status if task else "missing"
        output = (task.output_data or {}).get("text") if task else None
        duration_ms = _duration_ms(task)
        tokens = invocation.total_tokens if invocation else 0
        cost = invocation.estimated_cost_usd if invocation else None
        total_tokens += tokens
        total_cost += cost or 0
        total_duration_ms += duration_ms or 0
        agent = agents.get(step.assigned_agent_id)
        details.append(
            {
                "sequence": step.sequence,
                "title": step.title,
                "objective": step.objective,
                "status": task_status,
                "agent_id": step.assigned_agent_id,
                "agent_name": agent.name if agent else None,
                "output": output if isinstance(output, str) else None,
                "error": task.error_message if task else "Task record is missing",
                "model": invocation.model if invocation else None,
                "provider": invocation.provider if invocation else None,
                "tokens": tokens,
                "estimated_cost_usd": cost,
                "latency_ms": invocation.latency_ms if invocation else None,
                "duration_ms": duration_ms,
            }
        )
        if step.assigned_agent_id is None:
            risks.append(f"No agent matches step {step.sequence}: {step.title}")
        if task_status in {"failed", "missing"}:
            risks.append(f"Step {step.sequence} is {task_status}: {step.title}")

    approval = run.context["owner_command"].get("approval_status")
    if approval != "approved":
        next_action = "Review the plan and approve the command"
    elif run.status in {"planned", "active"}:
        next_action = "Execute or resume the approved command"
    elif run.status == "succeeded" and not outcome["promotable"]:
        next_action = "Resolve or rerun the unverified outcome before promotion"
    else:
        next_action = "Review outcomes and choose the next objective"
    outcome = assess_command_outcome(session, run=run).to_dict()
    if run.status == "succeeded" and not outcome["promotable"]:
        risks.extend(outcome["reasons"])

    planner = (run.context or {}).get("planner", {})
    planner_tokens = int((planner.get("usage") or {}).get("total_tokens") or 0)
    return {
        "command_id": str(run.id),
        "objective": run.objective,
        "status": run.status,
        "approval_status": approval,
        "promotion": run.context["owner_command"].get("promotion"),
        "outcome": outcome,
        "planner": planner,
        "readiness": "blocked" if risks else "ready",
        "progress": {
            "completed": sum(item["status"] == "succeeded" for item in details),
            "total": len(details),
        },
        "usage": {
            "planner_tokens": planner_tokens,
            "execution_tokens": total_tokens,
            "total_tokens": planner_tokens + total_tokens,
            "estimated_cost_usd": round(total_cost, 8),
            "execution_duration_ms": total_duration_ms,
        },
        "risks": risks,
        "recommended_next_action": next_action,
        "steps": details,
    }
