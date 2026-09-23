from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.agent import Agent
from backend.app.models.model_invocation import ModelInvocation
from backend.app.models.organization_kernel import OrganizationProject
from backend.app.models.seldrune_gpt_message import SeldruneGPTMessage
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task
from backend.app.services.outcome_verification import assess_command_outcome
from backend.app.services.portfolio_governor import reserved_project_budget


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
    organization_agents = list(
        session.scalars(
            select(Agent).where(Agent.organization_id == organization_id)
        )
    )
    organization_tasks = list(
        session.scalars(
            select(Task).where(Task.organization_id == organization_id)
        )
    )
    organization_invocations = list(
        session.scalars(
            select(ModelInvocation).where(
                ModelInvocation.organization_id == organization_id
            )
        )
    )
    gpt_messages = list(
        session.scalars(
            select(SeldruneGPTMessage).where(
                SeldruneGPTMessage.organization_id == organization_id,
                SeldruneGPTMessage.role == "assistant",
            )
        )
    )
    agent_performance: list[dict[str, Any]] = []
    for agent in organization_agents:
        agent_tasks = [
            task for task in organization_tasks if task.assigned_agent_id == agent.id
        ]
        agent_invocations = [
            item for item in organization_invocations if item.agent_id == agent.id
        ]
        succeeded = sum(task.status == "succeeded" for task in agent_tasks)
        failed = sum(task.status == "failed" for task in agent_tasks)
        completed = succeeded + failed + sum(
            task.status == "cancelled" for task in agent_tasks
        )
        total_cost = round(
            sum(item.estimated_cost_usd or 0 for item in agent_invocations),
            8,
        )
        latencies = [
            item.latency_ms for item in agent_invocations if item.latency_ms is not None
        ]
        agent_performance.append(
            {
                "agent_id": str(agent.id),
                "name": agent.name,
                "slug": agent.slug,
                "status": agent.status,
                "assigned_tasks": len(agent_tasks),
                "completed_tasks": completed,
                "succeeded_tasks": succeeded,
                "failed_tasks": failed,
                "success_rate": round(succeeded / completed, 4) if completed else None,
                "model_invocations": len(agent_invocations),
                "total_tokens": sum(item.total_tokens for item in agent_invocations),
                "estimated_cost_usd": total_cost,
                "cost_per_success_usd": (
                    round(total_cost / succeeded, 8) if succeeded else None
                ),
                "average_latency_ms": (
                    round(sum(latencies) / len(latencies)) if latencies else None
                ),
            }
        )
    agent_performance.sort(
        key=lambda item: (
            item["succeeded_tasks"],
            item["success_rate"] or 0,
            item["assigned_tasks"],
        ),
        reverse=True,
    )

    projects = list(
        session.scalars(
            select(OrganizationProject).where(
                OrganizationProject.organization_id == organization_id,
                OrganizationProject.status != "cancelled",
            )
        )
    )
    metered_projects = [project for project in projects if project.budget_limit_usd > 0]
    allocated_budget = round(
        sum(project.budget_limit_usd for project in metered_projects),
        8,
    )
    spent_budget = round(
        sum(project.budget_spent_usd for project in metered_projects),
        8,
    )
    reserved_budget = round(
        sum(reserved_project_budget(project) for project in metered_projects),
        8,
    )
    committed_budget = round(spent_budget + reserved_budget, 8)
    available_budget = round(max(allocated_budget - committed_budget, 0), 8)

    incidents: list[dict[str, Any]] = []
    for task in organization_tasks:
        if task.status == "failed":
            incidents.append(
                {
                    "type": "task_failed",
                    "severity": "critical",
                    "title": task.title,
                    "detail": task.error_message or "Agent task failed",
                    "resource_id": str(task.id),
                    "occurred_at": task.completed_at or task.updated_at,
                }
            )
    for invocation in organization_invocations:
        if invocation.status == "failed":
            incidents.append(
                {
                    "type": "model_invocation_failed",
                    "severity": "critical",
                    "title": f"{invocation.provider} model invocation failed",
                    "detail": invocation.error_message or "Model provider request failed",
                    "resource_id": str(invocation.id),
                    "occurred_at": invocation.completed_at or invocation.created_at,
                }
            )
    for run in commands:
        execution = (run.summary or {}).get("autonomous_execution") or {}
        if execution.get("halted_reason") == "budget_reservation_exceeded":
            incidents.append(
                {
                    "type": "budget_circuit_breaker",
                    "severity": "warning",
                    "title": "Budget circuit breaker stopped execution",
                    "detail": run.objective,
                    "resource_id": str(run.id),
                    "occurred_at": run.updated_at,
                }
            )
    for project in projects:
        if project.status == "blocked":
            incidents.append(
                {
                    "type": "project_blocked",
                    "severity": "warning",
                    "title": project.name,
                    "detail": "Project delivery is blocked and requires owner review",
                    "resource_id": str(project.id),
                    "occurred_at": project.updated_at,
                }
            )
    incidents.sort(key=lambda item: item["occurred_at"], reverse=True)
    incident_counts = {
        "critical": sum(item["severity"] == "critical" for item in incidents),
        "warning": sum(item["severity"] == "warning" for item in incidents),
    }

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
        "operational_incidents": {
            "total": len(incidents),
            "critical": incident_counts["critical"],
            "warning": incident_counts["warning"],
            "recent": incidents[:20],
        },
        "agent_performance": {
            "agent_count": len(organization_agents),
            "active_agent_count": sum(
                agent.status == "active" for agent in organization_agents
            ),
            "ranked_agents": agent_performance[:8],
        },
        "treasury": {
            "project_count": len(projects),
            "metered_project_count": len(metered_projects),
            "unmetered_project_count": len(projects) - len(metered_projects),
            "allocated_budget_usd": allocated_budget,
            "spent_budget_usd": spent_budget,
            "reserved_budget_usd": reserved_budget,
            "committed_budget_usd": committed_budget,
            "available_budget_usd": available_budget,
            "utilization": (
                round(committed_budget / allocated_budget, 4)
                if allocated_budget > 0
                else 0
            ),
            "overcommitted": committed_budget > allocated_budget,
        },
        "usage": {
            "model_invocations": (
                len(organization_invocations)
                + sum(item.model_calls for item in gpt_messages)
            ),
            "agent_model_invocations": len(organization_invocations),
            "direct_gpt_model_calls": sum(
                item.model_calls for item in gpt_messages
            ),
            "total_tokens": (
                sum(item.total_tokens for item in organization_invocations)
                + sum(
                    item.input_tokens + item.output_tokens
                    for item in gpt_messages
                )
            ),
            "cached_input_tokens": sum(
                item.cached_input_tokens for item in gpt_messages
            ),
            "estimated_cost_usd": round(
                sum(
                    item.estimated_cost_usd or 0
                    for item in organization_invocations
                )
                + sum(
                    item.estimated_cost_usd or 0
                    for item in gpt_messages
                ),
                6,
            ),
        },
        "recent_commands": [
            {
                "id": str(run.id),
                "objective": run.objective,
                "status": run.status,
                "approval_status": run.context["owner_command"].get("approval_status"),
                "forecast_cost_usd": float(
                    (
                        ((run.context or {}).get("project_delivery") or {}).get(
                            "cost_forecast"
                        )
                        or {}
                    ).get("estimated_execution_cost_usd")
                    or 0
                ),
                "reservation": (
                    ((run.context or {}).get("portfolio_governor") or {}).get(
                        "budget_reservation"
                    )
                ),
                "recorded_cost_usd": float(
                    ((run.summary or {}).get("autonomous_execution") or {}).get(
                        "recorded_cost_usd"
                    )
                    or 0
                ),
                "budget_halted": (
                    ((run.summary or {}).get("autonomous_execution") or {}).get(
                        "halted_reason"
                    )
                    == "budget_reservation_exceeded"
                ),
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
        task_output = (task.output_data or {}) if task else {}
        output = task_output.get("text")
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
                "execution_type": task_output.get("execution_type"),
                "tool_slug": task_output.get("tool_slug"),
                "tool_id": task_output.get("tool_id"),
                "tool_run_id": task_output.get("tool_run_id"),
                "tool_output": task_output.get("tool_output"),
                "evidence": task_output.get("evidence"),
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

    outcome = assess_command_outcome(session, run=run).to_dict()
    if run.status == "succeeded" and not outcome["promotable"]:
        risks.extend(outcome["reasons"])

    delivery = (run.context or {}).get("project_delivery") or {}
    cost_forecast = delivery.get("cost_forecast") or {}
    forecast_cost = float(cost_forecast.get("estimated_execution_cost_usd") or 0)
    budget_limit = float(delivery.get("budget_limit_usd") or 0)
    budget_spent = float(delivery.get("budget_spent_usd") or 0)
    if budget_limit > 0 and forecast_cost > max(budget_limit - budget_spent, 0):
        risks.append(
            f"Forecast cost USD {forecast_cost:.2f} exceeds remaining project budget"
        )

    governor = (run.context or {}).get("portfolio_governor") or {}
    reservation = governor.get("budget_reservation")
    runtime_budget = (run.summary or {}).get("autonomous_execution") or {}
    budget_control = {
        "forecast_cost_usd": forecast_cost,
        "reservation": reservation,
        "recorded_cost_usd": float(runtime_budget.get("recorded_cost_usd") or total_cost),
        "estimated_next_step_usd": float(
            runtime_budget.get("estimated_next_step_usd") or 0
        ),
        "halted": runtime_budget.get("halted_reason")
        == "budget_reservation_exceeded",
    }

    approval = run.context["owner_command"].get("approval_status")
    if approval != "approved" and any(risk.startswith("Forecast cost") for risk in risks):
        next_action = "Adjust project resources before approval"
    elif approval != "approved":
        next_action = "Review the plan and approve the command"
    elif run.status in {"planned", "active"}:
        next_action = "Execute or resume the approved command"
    elif run.status == "succeeded" and not outcome["promotable"]:
        next_action = "Resolve or rerun the unverified outcome before promotion"
    else:
        next_action = "Review outcomes and choose the next objective"
    planner = (run.context or {}).get("planner", {})
    planner_tokens = int((planner.get("usage") or {}).get("total_tokens") or 0)
    return {
        "command_id": str(run.id),
        "objective": run.objective,
        "status": run.status,
        "approval_status": approval,
        "promotion": run.context["owner_command"].get("promotion"),
        "recovery_command_id": run.context["owner_command"].get("recovery_command_id"),
        "outcome": outcome,
        "planner": planner,
        "cost_forecast": cost_forecast or None,
        "budget_control": budget_control,
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
