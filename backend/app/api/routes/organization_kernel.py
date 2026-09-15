from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _to_public
from backend.app.core.rbac import Permission
from backend.app.models.agent import Agent
from backend.app.models.membership import Membership
from backend.app.models.organization_kernel import (
    Department,
    DepartmentDelegation,
    OrganizationGoal,
    OrganizationProject,
)
from backend.app.schemas.orchestration import OrchestrationRunPublic
from backend.app.schemas.organization_kernel import (
    DelegationCreate,
    DelegationPublic,
    DelegationUpdate,
    DepartmentCreate,
    DepartmentPublic,
    DepartmentUpdate,
    GoalCreate,
    GoalPublic,
    GoalUpdate,
    ProjectCreate,
    ProjectPublic,
    ProjectUpdate,
)
from backend.app.services.audit import record_audit
from backend.app.services.founding_agents import ensure_founding_agents
from backend.app.services.project_delivery import (
    ProjectDeliveryError,
    create_project_recovery,
    launch_project_delivery,
)
from backend.app.services.organization_kernel import (
    build_organization_snapshot,
    ensure_founding_departments,
)

router = APIRouter(prefix="/organizations", tags=["organization-kernel"])
ReadDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_READ))]
ManageDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_MANAGE))]


def _belongs(instance: Any, organization_id: UUID, label: str):
    if instance is None or instance.organization_id != organization_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return instance


def _department(session: SessionDep, organization_id: UUID, item_id: UUID) -> Department:
    return _belongs(session.get(Department, item_id), organization_id, "Department")


def _goal(session: SessionDep, organization_id: UUID, item_id: UUID) -> OrganizationGoal:
    return _belongs(session.get(OrganizationGoal, item_id), organization_id, "Goal")


def _project(session: SessionDep, organization_id: UUID, item_id: UUID) -> OrganizationProject:
    return _belongs(session.get(OrganizationProject, item_id), organization_id, "Project")


def _delegation(
    session: SessionDep, organization_id: UUID, item_id: UUID
) -> DepartmentDelegation:
    return _belongs(session.get(DepartmentDelegation, item_id), organization_id, "Delegation")


def _agent(session: SessionDep, organization_id: UUID, item_id: UUID | None) -> Agent | None:
    if item_id is None:
        return None
    return _belongs(session.get(Agent, item_id), organization_id, "Agent")


def _apply_patch(instance: Any, payload: Any) -> None:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(instance, key, value)


def _audit(
    session: SessionDep,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID,
    details: dict[str, Any] | None = None,
) -> None:
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        details=details or {},
    )


@router.post("/{organization_id}/organization-kernel/bootstrap", response_model=dict[str, Any])
def bootstrap_organization_kernel(
    organization_id: UUID,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, Any]:
    ensure_founding_agents(
        session,
        organization_id=organization_id,
        created_by_user_id=current_user.id,
    )
    created = ensure_founding_departments(
        session,
        organization_id=organization_id,
        created_by_user_id=current_user.id,
    )
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="organization_kernel.bootstrapped",
        resource_type="organization",
        resource_id=str(organization_id),
        details={"departments_created": len(created)},
    )
    session.commit()
    return {
        "created_departments": len(created),
        "snapshot": build_organization_snapshot(session, organization_id),
    }


@router.get("/{organization_id}/organization-kernel", response_model=dict[str, Any])
def get_organization_kernel(
    organization_id: UUID,
    _membership: ReadDep,
    session: SessionDep,
) -> dict[str, Any]:
    return build_organization_snapshot(session, organization_id)


@router.post(
    "/{organization_id}/departments",
    response_model=DepartmentPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    organization_id: UUID,
    payload: DepartmentCreate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Department:
    existing = session.scalar(
        select(Department).where(
            Department.organization_id == organization_id,
            Department.slug == payload.slug,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Department slug already exists")
    _agent(session, organization_id, payload.owner_agent_id)
    department = Department(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    session.add(department)
    session.flush()
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="department.created",
        resource_type="department",
        resource_id=department.id,
        details={"slug": department.slug},
    )
    session.commit()
    session.refresh(department)
    return department


@router.get("/{organization_id}/departments", response_model=list[DepartmentPublic])
def list_departments(
    organization_id: UUID,
    _membership: ReadDep,
    session: SessionDep,
) -> list[Department]:
    return list(
        session.scalars(
            select(Department)
            .where(Department.organization_id == organization_id)
            .order_by(Department.priority.desc(), Department.name)
        )
    )


@router.patch("/{organization_id}/departments/{department_id}", response_model=DepartmentPublic)
def update_department(
    organization_id: UUID,
    department_id: UUID,
    payload: DepartmentUpdate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Department:
    department = _department(session, organization_id, department_id)
    if "owner_agent_id" in payload.model_fields_set:
        _agent(session, organization_id, payload.owner_agent_id)
    _apply_patch(department, payload)
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="department.updated",
        resource_type="department",
        resource_id=department.id,
    )
    session.commit()
    session.refresh(department)
    return department


@router.post(
    "/{organization_id}/goals",
    response_model=GoalPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    organization_id: UUID,
    payload: GoalCreate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrganizationGoal:
    if payload.department_id is not None:
        _department(session, organization_id, payload.department_id)
    if payload.parent_goal_id is not None:
        _goal(session, organization_id, payload.parent_goal_id)
    _agent(session, organization_id, payload.owner_agent_id)
    goal = OrganizationGoal(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    session.add(goal)
    session.flush()
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="organization_goal.created",
        resource_type="organization_goal",
        resource_id=goal.id,
    )
    session.commit()
    session.refresh(goal)
    return goal


@router.get("/{organization_id}/goals", response_model=list[GoalPublic])
def list_goals(
    organization_id: UUID,
    _membership: ReadDep,
    session: SessionDep,
) -> list[OrganizationGoal]:
    return list(
        session.scalars(
            select(OrganizationGoal)
            .where(OrganizationGoal.organization_id == organization_id)
            .order_by(OrganizationGoal.priority.desc(), OrganizationGoal.created_at.desc())
        )
    )


@router.patch("/{organization_id}/goals/{goal_id}", response_model=GoalPublic)
def update_goal(
    organization_id: UUID,
    goal_id: UUID,
    payload: GoalUpdate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrganizationGoal:
    goal = _goal(session, organization_id, goal_id)
    if "department_id" in payload.model_fields_set and payload.department_id is not None:
        _department(session, organization_id, payload.department_id)
    if "parent_goal_id" in payload.model_fields_set and payload.parent_goal_id is not None:
        if payload.parent_goal_id == goal.id:
            raise HTTPException(status_code=422, detail="Goal cannot be its own parent")
        _goal(session, organization_id, payload.parent_goal_id)
    if "owner_agent_id" in payload.model_fields_set:
        _agent(session, organization_id, payload.owner_agent_id)
    _apply_patch(goal, payload)
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="organization_goal.updated",
        resource_type="organization_goal",
        resource_id=goal.id,
    )
    session.commit()
    session.refresh(goal)
    return goal


@router.post(
    "/{organization_id}/projects",
    response_model=ProjectPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    organization_id: UUID,
    payload: ProjectCreate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrganizationProject:
    existing = session.scalar(
        select(OrganizationProject).where(
            OrganizationProject.organization_id == organization_id,
            OrganizationProject.slug == payload.slug,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Project slug already exists")
    if payload.department_id is not None:
        _department(session, organization_id, payload.department_id)
    if payload.goal_id is not None:
        _goal(session, organization_id, payload.goal_id)
    _agent(session, organization_id, payload.lead_agent_id)
    project = OrganizationProject(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    session.add(project)
    session.flush()
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="organization_project.created",
        resource_type="organization_project",
        resource_id=project.id,
        details={"slug": project.slug},
    )
    session.commit()
    session.refresh(project)
    return project


@router.get("/{organization_id}/projects", response_model=list[ProjectPublic])
def list_projects(
    organization_id: UUID,
    _membership: ReadDep,
    session: SessionDep,
) -> list[OrganizationProject]:
    return list(
        session.scalars(
            select(OrganizationProject)
            .where(OrganizationProject.organization_id == organization_id)
            .order_by(OrganizationProject.priority.desc(), OrganizationProject.created_at.desc())
        )
    )


@router.patch("/{organization_id}/projects/{project_id}", response_model=ProjectPublic)
def update_project(
    organization_id: UUID,
    project_id: UUID,
    payload: ProjectUpdate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrganizationProject:
    project = _project(session, organization_id, project_id)
    if "department_id" in payload.model_fields_set and payload.department_id is not None:
        _department(session, organization_id, payload.department_id)
    if "goal_id" in payload.model_fields_set and payload.goal_id is not None:
        _goal(session, organization_id, payload.goal_id)
    if "lead_agent_id" in payload.model_fields_set:
        _agent(session, organization_id, payload.lead_agent_id)
    _apply_patch(project, payload)
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="organization_project.updated",
        resource_type="organization_project",
        resource_id=project.id,
    )
    session.commit()
    session.refresh(project)
    return project


@router.post(
    "/{organization_id}/projects/{project_id}/launch",
    response_model=OrchestrationRunPublic,
    status_code=status.HTTP_201_CREATED,
)
def launch_project(
    organization_id: UUID,
    project_id: UUID,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrchestrationRunPublic:
    project = _project(session, organization_id, project_id)
    try:
        command = launch_project_delivery(
            session,
            project=project,
            actor_user_id=current_user.id,
        )
    except ProjectDeliveryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    session.refresh(command)
    return _to_public(session, command)


@router.post(
    "/{organization_id}/projects/{project_id}/recover",
    response_model=OrchestrationRunPublic,
    status_code=status.HTTP_201_CREATED,
)
def recover_project(
    organization_id: UUID,
    project_id: UUID,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> OrchestrationRunPublic:
    project = _project(session, organization_id, project_id)
    try:
        command = create_project_recovery(
            session,
            project=project,
            actor_user_id=current_user.id,
        )
    except ProjectDeliveryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    session.refresh(command)
    return _to_public(session, command)


@router.post(
    "/{organization_id}/delegations",
    response_model=DelegationPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_delegation(
    organization_id: UUID,
    payload: DelegationCreate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> DepartmentDelegation:
    if payload.source_department_id == payload.target_department_id:
        raise HTTPException(status_code=422, detail="Delegation requires two departments")
    _department(session, organization_id, payload.source_department_id)
    _department(session, organization_id, payload.target_department_id)
    if payload.project_id is not None:
        _project(session, organization_id, payload.project_id)
    if payload.goal_id is not None:
        _goal(session, organization_id, payload.goal_id)
    _agent(session, organization_id, payload.assigned_agent_id)
    delegation = DepartmentDelegation(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    session.add(delegation)
    session.flush()
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="department_delegation.created",
        resource_type="department_delegation",
        resource_id=delegation.id,
    )
    session.commit()
    session.refresh(delegation)
    return delegation


@router.get("/{organization_id}/delegations", response_model=list[DelegationPublic])
def list_delegations(
    organization_id: UUID,
    _membership: ReadDep,
    session: SessionDep,
) -> list[DepartmentDelegation]:
    return list(
        session.scalars(
            select(DepartmentDelegation)
            .where(DepartmentDelegation.organization_id == organization_id)
            .order_by(
                DepartmentDelegation.priority.desc(),
                DepartmentDelegation.created_at.desc(),
            )
        )
    )


@router.patch("/{organization_id}/delegations/{delegation_id}", response_model=DelegationPublic)
def update_delegation(
    organization_id: UUID,
    delegation_id: UUID,
    payload: DelegationUpdate,
    _membership: ManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> DepartmentDelegation:
    delegation = _delegation(session, organization_id, delegation_id)
    if "assigned_agent_id" in payload.model_fields_set:
        _agent(session, organization_id, payload.assigned_agent_id)
    _apply_patch(delegation, payload)
    _audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="department_delegation.updated",
        resource_type="department_delegation",
        resource_id=delegation.id,
    )
    session.commit()
    session.refresh(delegation)
    return delegation
