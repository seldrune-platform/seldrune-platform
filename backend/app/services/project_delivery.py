from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.model_invocation import ModelInvocation
from backend.app.models.organization_kernel import OrganizationGoal, OrganizationProject
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task
from backend.app.services.adaptive_planning import build_adaptive_planning_guidance
from backend.app.services.audit import record_audit
from backend.app.services.founding_agents import ensure_founding_agents
from backend.app.services.live_planner import build_live_plan
from backend.app.services.orchestrator import create_orchestration_run
from backend.app.services.outcome_verification import assess_command_outcome
from backend.app.services.playbook_engine import consolidate_playbooks
from backend.app.services.playbook_guidance import build_playbook_guidance
from backend.app.services.playbook_overlay import merge_playbook


class ProjectDeliveryError(RuntimeError):
    pass


def launch_project_delivery(
    session: Session,
    *,
    project: OrganizationProject,
    actor_user_id: UUID,
) -> OrchestrationRun:
    if project.status in {"completed", "cancelled"}:
        raise ProjectDeliveryError(f"A {project.status} project cannot be launched")

    existing_id = (project.metadata_json or {}).get("delivery_command_id")
    if existing_id:
        existing = session.get(OrchestrationRun, UUID(existing_id))
        if existing is not None and existing.organization_id == project.organization_id:
            return existing

    objective = (
        f'Deliver the organization project "{project.name}". '
        f"Project scope: {project.description or project.name}. "
        "Create and execute a concrete, evidence-based delivery plan within the recorded "
        f"budget limit of USD {project.budget_limit_usd:.2f} and resource limit of "
        f"{project.resource_limit_units} units. Stop before any unapproved external action."
    )[:4000]
    ensure_founding_agents(
        session,
        organization_id=project.organization_id,
        created_by_user_id=actor_user_id,
    )
    consolidate_playbooks(
        session,
        organization_id=project.organization_id,
        actor_user_id=actor_user_id,
    )
    playbook_guidance = build_playbook_guidance(
        session,
        organization_id=project.organization_id,
        objective=objective,
    )
    adaptive_guidance = build_adaptive_planning_guidance(
        session,
        organization_id=project.organization_id,
        objective=objective,
    )
    guidance = merge_playbook(adaptive_guidance, playbook_guidance)
    planned = build_live_plan(objective, adaptive_guidance=guidance)
    context = {
        "owner_command": {
            "approval_status": "awaiting_approval",
            "approved_by": None,
        },
        "planner": planned.metadata,
        "operational_playbook": playbook_guidance,
        "project_delivery": {
            "project_id": str(project.id),
            "goal_id": str(project.goal_id) if project.goal_id else None,
            "department_id": str(project.department_id) if project.department_id else None,
            "budget_limit_usd": project.budget_limit_usd,
            "resource_limit_units": project.resource_limit_units,
        },
    }
    command = create_orchestration_run(
        session,
        organization_id=project.organization_id,
        created_by_user_id=actor_user_id,
        objective=objective,
        context=context,
        plan=planned.steps,
    )
    command.planner_version = planned.planner_version
    project.status = "active"
    project.start_at = project.start_at or datetime.now(UTC)
    project.metadata_json = {
        **(project.metadata_json or {}),
        "delivery_command_id": str(command.id),
        "delivery_state": "awaiting_owner_approval",
    }
    goal = session.get(OrganizationGoal, project.goal_id) if project.goal_id else None
    if (
        goal is not None
        and goal.organization_id == project.organization_id
        and goal.status == "planned"
    ):
        goal.status = "active"

    record_audit(
        session,
        organization_id=project.organization_id,
        actor_user_id=actor_user_id,
        action="organization_project.delivery_launched",
        resource_type="organization_project",
        resource_id=str(project.id),
        details={
            "delivery_command_id": str(command.id),
            "goal_id": str(project.goal_id) if project.goal_id else None,
            "step_count": len(planned.steps),
            "approval_status": "awaiting_approval",
        },
    )
    return command



def sync_project_delivery_outcome(
    session: Session,
    *,
    run: OrchestrationRun,
    actor_user_id: UUID,
) -> dict[str, object] | None:
    delivery = (run.context or {}).get("project_delivery") or {}
    project_id = delivery.get("project_id")
    if not project_id or run.status != "succeeded":
        return None
    project = session.get(OrganizationProject, UUID(project_id))
    if project is None or project.organization_id != run.organization_id:
        return None
    if (project.metadata_json or {}).get("delivery_synced_command_id") == str(run.id):
        return (project.metadata_json or {}).get("delivery_outcome")

    assessment = assess_command_outcome(session, run=run)
    status_by_verdict = {
        "achieved": "completed",
        "review": "paused",
        "not_achieved": "blocked",
    }
    state_by_verdict = {
        "achieved": "verified_complete",
        "review": "owner_review_required",
        "not_achieved": "outcome_blocked",
    }
    project.status = status_by_verdict[assessment.verdict]

    steps = list(
        session.scalars(
            select(OrchestrationStep).where(
                OrchestrationStep.orchestration_run_id == run.id
            )
        )
    )
    task_ids = [step.task_id for step in steps]
    invocations = (
        list(
            session.scalars(
                select(ModelInvocation).where(ModelInvocation.task_id.in_(task_ids))
            )
        )
        if task_ids
        else []
    )
    successful_units = sum(
        (task := session.get(Task, task_id)) is not None and task.status == "succeeded"
        for task_id in task_ids
    )
    recorded_cost = round(
        sum(invocation.estimated_cost_usd or 0 for invocation in invocations),
        8,
    )
    outcome = assessment.to_dict()
    project.budget_spent_usd = round(project.budget_spent_usd + recorded_cost, 8)
    project.resource_used_units += successful_units
    project.metadata_json = {
        **(project.metadata_json or {}),
        "delivery_state": state_by_verdict[assessment.verdict],
        "delivery_outcome": outcome,
        "delivery_synced_command_id": str(run.id),
        "delivery_recorded_cost_usd": recorded_cost,
        "delivery_resource_units": successful_units,
    }

    goal = session.get(OrganizationGoal, project.goal_id) if project.goal_id else None
    if goal is not None and goal.organization_id == project.organization_id:
        goal_projects = list(
            session.scalars(
                select(OrganizationProject).where(
                    OrganizationProject.organization_id == project.organization_id,
                    OrganizationProject.goal_id == goal.id,
                )
            )
        )
        if goal_projects and all(item.status == "completed" for item in goal_projects):
            goal.status = "achieved"
            if goal.target_value is not None:
                goal.current_value = goal.target_value
        elif assessment.verdict == "not_achieved":
            goal.status = "blocked"

    record_audit(
        session,
        organization_id=project.organization_id,
        actor_user_id=actor_user_id,
        action="organization_project.delivery_synchronized",
        resource_type="organization_project",
        resource_id=str(project.id),
        details={
            "delivery_command_id": str(run.id),
            "project_status": project.status,
            "outcome": outcome,
            "recorded_cost_usd": recorded_cost,
            "resource_units": successful_units,
        },
    )
    return outcome
