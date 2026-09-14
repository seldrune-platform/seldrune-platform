from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.organization_kernel import (
    Department,
    OrganizationGoal,
    OrganizationProject,
)
from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.services.audit import record_audit
from backend.app.services.organization_kernel import ensure_founding_departments

_CAPABILITY_DEPARTMENT = {
    "research": "research-intelligence",
    "analysis": "research-intelligence",
    "architecture": "engineering-automation",
    "engineering": "engineering-automation",
    "validation": "operations",
}


class CommandPromotionError(RuntimeError):
    pass


def _select_department(
    session: Session,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> Department | None:
    steps = list(
        session.scalars(
            select(OrchestrationStep).where(
                OrchestrationStep.orchestration_run_id == run_id
            )
        )
    )
    votes: Counter[str] = Counter()
    for step in steps:
        for capability in step.required_capabilities:
            slug = _CAPABILITY_DEPARTMENT.get(capability.strip().lower())
            if slug:
                votes[slug] += 1
    preferred = votes.most_common(1)[0][0] if votes else "executive-office"
    return session.scalar(
        select(Department).where(
            Department.organization_id == organization_id,
            Department.slug == preferred,
        )
    )


def promote_command_to_project(
    session: Session,
    *,
    run: OrchestrationRun,
    actor_user_id: UUID,
) -> dict[str, Any]:
    if run.status != "succeeded":
        raise CommandPromotionError("Only a succeeded command can be promoted")

    owner_command = (run.context or {}).get("owner_command") or {}
    existing = owner_command.get("promotion") or {}
    project_id = existing.get("project_id")
    goal_id = existing.get("goal_id")
    if project_id and goal_id:
        project = session.get(OrganizationProject, UUID(project_id))
        goal = session.get(OrganizationGoal, UUID(goal_id))
        if (
            project is not None
            and goal is not None
            and project.organization_id == run.organization_id
            and goal.organization_id == run.organization_id
        ):
            return {
                "created": False,
                "goal": goal,
                "project": project,
                "department_id": project.department_id,
            }

    ensure_founding_departments(
        session,
        organization_id=run.organization_id,
        created_by_user_id=actor_user_id,
    )
    department = _select_department(
        session,
        organization_id=run.organization_id,
        run_id=run.id,
    )
    source = {"source": "owner_command", "owner_command_id": str(run.id)}
    goal = OrganizationGoal(
        organization_id=run.organization_id,
        department_id=department.id if department else None,
        created_by_user_id=actor_user_id,
        title=run.objective[:240],
        description=(
            "Governed follow-through created from a successfully completed "
            "Seldrune owner command."
        ),
        status="planned",
        priority=70,
        metadata_json=source,
    )
    session.add(goal)
    session.flush()

    project = OrganizationProject(
        organization_id=run.organization_id,
        department_id=department.id if department else None,
        goal_id=goal.id,
        created_by_user_id=actor_user_id,
        name=run.objective[:200],
        slug=f"command-{run.id.hex[:16]}",
        description=(
            "Execution project promoted from completed command results. "
            "Review scope, budget, capacity, and delivery milestones before activation."
        ),
        status="planned",
        priority=70,
        budget_limit_usd=0.0,
        resource_limit_units=100,
        metadata_json={
            **source,
            "planner_version": run.planner_version,
            "step_count": (run.summary or {}).get("step_count", 0),
        },
    )
    session.add(project)
    session.flush()

    promotion = {
        "goal_id": str(goal.id),
        "project_id": str(project.id),
        "department_id": str(department.id) if department else None,
        "department_name": department.name if department else None,
    }
    run.context = {
        **(run.context or {}),
        "owner_command": {**owner_command, "promotion": promotion},
    }
    record_audit(
        session,
        organization_id=run.organization_id,
        actor_user_id=actor_user_id,
        action="owner_command.promoted",
        resource_type="orchestration",
        resource_id=str(run.id),
        details=promotion,
    )
    return {
        "created": True,
        "goal": goal,
        "project": project,
        "department_id": project.department_id,
    }
