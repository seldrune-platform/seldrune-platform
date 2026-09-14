from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.organization_kernel import (
    Department,
    DepartmentDelegation,
    OrganizationGoal,
    OrganizationProject,
)

_FOUNDING_DEPARTMENTS = (
    (
        "Executive Office",
        "executive-office",
        "Set organization priorities, allocate resources, and govern cross-functional execution.",
        100,
    ),
    (
        "Research & Intelligence",
        "research-intelligence",
        (
            "Continuously discover evidence, opportunities, risks, clients, markets, "
            "and better methods."
        ),
        90,
    ),
    (
        "Engineering & Automation",
        "engineering-automation",
        "Build reliable software, automations, agents, integrations, and internal infrastructure.",
        85,
    ),
    (
        "Operations",
        "operations",
        "Run repeatable service delivery, quality, controls, and day-to-day execution.",
        80,
    ),
    (
        "Growth & Partnerships",
        "growth-partnerships",
        "Develop clients, partnerships, commercial opportunities, and go-to-market systems.",
        75,
    ),
)


def ensure_founding_departments(
    session: Session,
    *,
    organization_id: UUID,
    created_by_user_id: UUID | None,
) -> list[Department]:
    existing = {
        department.slug: department
        for department in session.scalars(
            select(Department).where(Department.organization_id == organization_id)
        )
    }
    created: list[Department] = []
    for name, slug, mission, priority in _FOUNDING_DEPARTMENTS:
        if slug in existing:
            continue
        department = Department(
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            name=name,
            slug=slug,
            mission=mission,
            priority=priority,
            budget_limit_usd=0.0,
            resource_limit_units=100,
            metadata_json={"founding_department": True},
        )
        session.add(department)
        created.append(department)
    session.flush()
    return created


def _is_overdue(due_at: datetime | None, now: datetime) -> bool:
    if due_at is None:
        return False
    comparable = due_at if due_at.tzinfo is not None else due_at.replace(tzinfo=UTC)
    return comparable < now


def build_organization_snapshot(session: Session, organization_id: UUID) -> dict[str, Any]:
    departments = list(
        session.scalars(
            select(Department)
            .where(Department.organization_id == organization_id)
            .order_by(Department.priority.desc(), Department.name)
        )
    )
    goals = list(
        session.scalars(
            select(OrganizationGoal)
            .where(OrganizationGoal.organization_id == organization_id)
            .order_by(OrganizationGoal.priority.desc(), OrganizationGoal.created_at.desc())
        )
    )
    projects = list(
        session.scalars(
            select(OrganizationProject)
            .where(OrganizationProject.organization_id == organization_id)
            .order_by(OrganizationProject.priority.desc(), OrganizationProject.created_at.desc())
        )
    )
    delegations = list(
        session.scalars(
            select(DepartmentDelegation)
            .where(DepartmentDelegation.organization_id == organization_id)
            .order_by(DepartmentDelegation.priority.desc(), DepartmentDelegation.created_at.desc())
        )
    )

    active_projects = [project for project in projects if project.status == "active"]
    blocked_projects = [project for project in projects if project.status == "blocked"]
    open_goals = [goal for goal in goals if goal.status in {"planned", "active", "blocked"}]
    blocked_goals = [goal for goal in goals if goal.status == "blocked"]
    open_delegations = [
        delegation
        for delegation in delegations
        if delegation.status in {"proposed", "accepted", "in_progress"}
    ]
    budget_limit = sum(project.budget_limit_usd for project in active_projects)
    budget_spent = sum(project.budget_spent_usd for project in active_projects)
    resource_limit = sum(project.resource_limit_units for project in active_projects)
    resource_used = sum(project.resource_used_units for project in active_projects)
    now = datetime.now(UTC)
    overdue_projects = [project for project in active_projects if _is_overdue(project.due_at, now)]
    over_budget_projects = [
        project
        for project in active_projects
        if project.budget_limit_usd > 0 and project.budget_spent_usd > project.budget_limit_usd
    ]
    over_capacity_projects = [
        project
        for project in active_projects
        if project.resource_limit_units > 0
        and project.resource_used_units > project.resource_limit_units
    ]

    return {
        "counts": {
            "departments": len(departments),
            "goals": len(goals),
            "open_goals": len(open_goals),
            "blocked_goals": len(blocked_goals),
            "projects": len(projects),
            "active_projects": len(active_projects),
            "blocked_projects": len(blocked_projects),
            "overdue_projects": len(overdue_projects),
            "over_budget_projects": len(over_budget_projects),
            "over_capacity_projects": len(over_capacity_projects),
            "open_delegations": len(open_delegations),
        },
        "resources": {
            "active_project_budget_limit_usd": round(budget_limit, 2),
            "active_project_budget_spent_usd": round(budget_spent, 2),
            "budget_utilization": round(budget_spent / budget_limit, 3) if budget_limit else 0.0,
            "active_project_resource_limit_units": resource_limit,
            "active_project_resource_used_units": resource_used,
            "resource_utilization": round(resource_used / resource_limit, 3)
            if resource_limit
            else 0.0,
        },
        "priorities": {
            "top_departments": [
                {"id": str(item.id), "name": item.name, "priority": item.priority}
                for item in departments[:5]
            ],
            "top_goals": [
                {"id": str(item.id), "title": item.title, "priority": item.priority}
                for item in open_goals[:5]
            ],
            "top_projects": [
                {"id": str(item.id), "name": item.name, "priority": item.priority}
                for item in active_projects[:5]
            ],
        },
        "health": {
            "blocked_project_ratio": round(len(blocked_projects) / len(projects), 3)
            if projects
            else 0.0,
            "blocked_goal_ratio": round(len(blocked_goals) / len(open_goals), 3)
            if open_goals
            else 0.0,
            "overdue_project_ratio": round(len(overdue_projects) / len(active_projects), 3)
            if active_projects
            else 0.0,
            "over_budget_project_ratio": round(len(over_budget_projects) / len(active_projects), 3)
            if active_projects
            else 0.0,
            "over_capacity_project_ratio": round(
                len(over_capacity_projects) / len(active_projects), 3
            )
            if active_projects
            else 0.0,
        },
    }
