from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.organization_kernel import OrganizationProject
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task


class PortfolioGovernorError(RuntimeError):
    pass


def evaluate_project_execution(
    session: Session,
    *,
    project: OrganizationProject,
    run: OrchestrationRun,
) -> dict[str, Any]:
    pending_steps = list(
        session.scalars(
            select(OrchestrationStep)
            .join(Task, Task.id == OrchestrationStep.task_id)
            .where(
                OrchestrationStep.orchestration_run_id == run.id,
                Task.status.notin_({"succeeded", "cancelled"}),
            )
        )
    )
    required_units = len(pending_steps)
    remaining_units = max(project.resource_limit_units - project.resource_used_units, 0)
    budget_configured = project.budget_limit_usd > 0
    remaining_budget = (
        round(max(project.budget_limit_usd - project.budget_spent_usd, 0), 8)
        if budget_configured
        else None
    )
    reasons: list[str] = []
    if required_units > remaining_units:
        reasons.append(
            f"Plan requires {required_units} capacity units but only {remaining_units} remain"
        )
    if budget_configured and project.budget_spent_usd >= project.budget_limit_usd:
        reasons.append("Project budget is exhausted")

    decision = {
        "allowed": not reasons,
        "project_id": str(project.id),
        "command_id": str(run.id),
        "required_resource_units": required_units,
        "remaining_resource_units": remaining_units,
        "budget_limit_configured": budget_configured,
        "remaining_budget_usd": remaining_budget,
        "reasons": reasons,
    }
    if reasons:
        raise PortfolioGovernorError("; ".join(reasons))
    return decision
