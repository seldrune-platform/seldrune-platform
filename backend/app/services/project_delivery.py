from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.organization_kernel import OrganizationGoal, OrganizationProject
from backend.app.models.orchestration import OrchestrationRun
from backend.app.services.adaptive_planning import build_adaptive_planning_guidance
from backend.app.services.audit import record_audit
from backend.app.services.founding_agents import ensure_founding_agents
from backend.app.services.live_planner import build_live_plan
from backend.app.services.orchestrator import create_orchestration_run
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
    if goal is not None and goal.organization_id == project.organization_id and goal.status == "planned":
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
