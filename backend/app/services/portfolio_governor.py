from __future__ import annotations

from typing import Any

from backend.app.models.organization_kernel import OrganizationProject
from backend.app.models.orchestration import OrchestrationRun


class PortfolioGovernorError(RuntimeError):
    pass


def evaluate_project_execution(
    *,
    project: OrganizationProject | None,
    run: OrchestrationRun,
    delivery_context: dict[str, Any],
) -> dict[str, Any]:
    required_units = max(
        int((run.summary or {}).get("step_count", 0))
        - int((run.summary or {}).get("succeeded_steps", 0)),
        0,
    )
    resource_limit = (
        project.resource_limit_units
        if project is not None
        else int(delivery_context.get("resource_limit_units", 0))
    )
    resource_used = (
        project.resource_used_units
        if project is not None
        else int(delivery_context.get("resource_used_units", 0))
    )
    budget_limit = (
        project.budget_limit_usd
        if project is not None
        else float(delivery_context.get("budget_limit_usd", 0))
    )
    budget_spent = (
        project.budget_spent_usd
        if project is not None
        else float(delivery_context.get("budget_spent_usd", 0))
    )
    remaining_units = max(resource_limit - resource_used, 0)
    budget_configured = budget_limit > 0
    remaining_budget = (
        round(max(budget_limit - budget_spent, 0), 8) if budget_configured else None
    )
    reasons: list[str] = []
    if required_units > remaining_units:
        reasons.append(
            f"Plan requires {required_units} capacity units but only {remaining_units} remain"
        )
    if budget_configured and budget_spent >= budget_limit:
        reasons.append("Project budget is exhausted")

    decision = {
        "allowed": not reasons,
        "project_id": delivery_context.get("project_id"),
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
