from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.model_invocation import ModelInvocation
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task


def _commands(session: Session, organization_id: UUID) -> list[OrchestrationRun]:
    runs = list(session.scalars(select(OrchestrationRun).where(
        OrchestrationRun.organization_id == organization_id
    ).order_by(OrchestrationRun.created_at.desc())))
    return [run for run in runs if (run.context or {}).get("owner_command")]


def build_owner_dashboard(session: Session, organization_id: UUID) -> dict[str, Any]:
    commands = _commands(session, organization_id)
    run_ids = [run.id for run in commands]
    steps = list(session.scalars(select(OrchestrationStep).where(
        OrchestrationStep.orchestration_run_id.in_(run_ids)
    ))) if run_ids else []
    tasks = [task for step in steps if (task := session.get(Task, step.task_id)) is not None]
    task_ids = [task.id for task in tasks]
    invocations = list(session.scalars(select(ModelInvocation).where(
        ModelInvocation.task_id.in_(task_ids)
    ))) if task_ids else []
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
            {"id": str(run.id), "objective": run.objective, "status": run.status,
             "approval_status": run.context["owner_command"].get("approval_status"),
             "created_at": run.created_at}
            for run in commands[:10]
        ],
    }


def build_decision_brief(session: Session, run: OrchestrationRun) -> dict[str, Any]:
    steps = list(session.scalars(select(OrchestrationStep).where(
        OrchestrationStep.orchestration_run_id == run.id
    ).order_by(OrchestrationStep.sequence)))
    details = []
    risks = []
    for step in steps:
        task = session.get(Task, step.task_id)
        task_status = task.status if task else "missing"
        output = (task.output_data or {}).get("text") if task else None
        details.append({"sequence": step.sequence, "title": step.title,
                        "status": task_status, "agent_id": step.assigned_agent_id,
                        "output_excerpt": output[:500] if isinstance(output, str) else None})
        if step.assigned_agent_id is None:
            risks.append(f"No agent matches step {step.sequence}: {step.title}")
        if task_status in {"failed", "missing"}:
            risks.append(f"Step {step.sequence} is {task_status}: {step.title}")
    approval = run.context["owner_command"].get("approval_status")
    if approval != "approved":
        next_action = "Review the plan and approve the command"
    elif run.status in {"planned", "active"}:
        next_action = "Execute or resume the approved command"
    else:
        next_action = "Review outcomes and choose the next objective"
    planner = (run.context or {}).get("planner", {})
    return {"command_id": str(run.id), "objective": run.objective, "status": run.status,
            "approval_status": approval, "planner": planner,
            "readiness": "blocked" if risks else "ready",
            "progress": {"completed": sum(item["status"] == "succeeded" for item in details),
                         "total": len(details)}, "risks": risks,
            "recommended_next_action": next_action, "steps": details}
