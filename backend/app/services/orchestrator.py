from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.orchestration import ApprovalStatus, OrchestrationStatus, PlannedStep
from backend.app.core.tasking import AgentStatus, TERMINAL_TASK_STATUSES, TaskStatus
from backend.app.models.agent import Agent
from backend.app.models.organization_kernel import OrganizationProject
from backend.app.models.orchestration import (
    OrchestrationApproval,
    OrchestrationRun,
    OrchestrationStep,
)
from backend.app.models.task import Task, TaskEvent
from backend.app.services.audit import record_audit


class OrchestrationAttributionError(ValueError):
    pass


def normalize_capability(value: str) -> str:
    return "-".join(value.strip().lower().replace("_", " ").split())


def select_best_agent(
    agents: Iterable[Agent],
    required_capabilities: list[str],
    performance_evidence: dict[UUID, dict[str, float | int]] | None = None,
    required_tool_slug: str | None = None,
) -> tuple[Agent | None, int]:
    required = {normalize_capability(item) for item in required_capabilities if item.strip()}
    if not required:
        return None, 0

    evidence = performance_evidence or {}
    candidates: list[tuple[int, int, float, int, int, str, Agent]] = []
    for agent in agents:
        if agent.status != AgentStatus.ACTIVE.value:
            continue
        if (
            required_tool_slug
            and agent.allowed_tool_slugs is not None
            and required_tool_slug not in agent.allowed_tool_slugs
        ):
            continue
        available = {normalize_capability(item) for item in agent.capabilities}
        matched = len(required & available)
        if matched == 0:
            continue
        score = round((matched / len(required)) * 100)
        performance = evidence.get(agent.id, {})
        completed = int(performance.get("completed_tasks", 0))
        succeeded = int(performance.get("succeeded_tasks", 0))
        assigned = int(performance.get("assigned_tasks", 0))
        success_rate = succeeded / completed if completed else 0.0
        candidates.append(
            (
                score,
                int(completed > 0),
                success_rate,
                succeeded,
                -assigned,
                agent.slug,
                agent,
            )
        )

    if not candidates:
        return None, 0

    candidates.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            -item[2],
            -item[3],
            -item[4],
            item[5],
        )
    )
    score, _, _, _, _, _, agent = candidates[0]
    return agent, score


def build_agent_performance_evidence(
    session: Session,
    *,
    organization_id: UUID,
    agents: list[Agent],
) -> dict[UUID, dict[str, float | int]]:
    agent_ids = [agent.id for agent in agents]
    if not agent_ids:
        return {}
    tasks = list(
        session.scalars(
            select(Task).where(
                Task.organization_id == organization_id,
                Task.assigned_agent_id.in_(agent_ids),
            )
        )
    )
    evidence: dict[UUID, dict[str, float | int]] = {}
    for agent in agents:
        assigned = [task for task in tasks if task.assigned_agent_id == agent.id]
        completed = [
            task
            for task in assigned
            if task.status
            in {
                TaskStatus.SUCCEEDED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            }
        ]
        succeeded = sum(task.status == TaskStatus.SUCCEEDED.value for task in completed)
        evidence[agent.id] = {
            "assigned_tasks": len(assigned),
            "completed_tasks": len(completed),
            "succeeded_tasks": succeeded,
            "success_rate": round(succeeded / len(completed), 4) if completed else 0.0,
        }
    return evidence


def _validated_project_id(
    session: Session,
    *,
    organization_id: UUID,
    project_id: UUID | None,
) -> UUID | None:
    if project_id is None:
        return None
    project = session.get(OrganizationProject, project_id)
    if project is None or project.organization_id != organization_id:
        raise OrchestrationAttributionError("Project attribution does not belong to organization")
    return project.id


def create_orchestration_run(
    session: Session,
    *,
    organization_id: UUID,
    created_by_user_id: UUID,
    objective: str,
    context: dict,
    plan: list[PlannedStep],
    project_id: UUID | None = None,
) -> OrchestrationRun:
    project_id = _validated_project_id(
        session,
        organization_id=organization_id,
        project_id=project_id,
    )
    agents = list(
        session.scalars(
            select(Agent).where(
                Agent.organization_id == organization_id,
                Agent.status == AgentStatus.ACTIVE.value,
            )
        )
    )
    performance_evidence = build_agent_performance_evidence(
        session,
        organization_id=organization_id,
        agents=agents,
    )
    run = OrchestrationRun(
        organization_id=organization_id,
        created_by_user_id=created_by_user_id,
        objective=objective,
        context=context,
        status=OrchestrationStatus.PLANNED.value,
    )
    session.add(run)
    session.flush()

    matched_steps = 0
    approval_required_steps = 0
    for sequence, planned in enumerate(plan, start=1):
        agent, score = select_best_agent(
            agents,
            planned.required_capabilities,
            performance_evidence,
            planned.tool_slug,
        )
        task_status = TaskStatus.ASSIGNED if agent is not None else TaskStatus.QUEUED
        task = Task(
            organization_id=organization_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            assigned_agent_id=agent.id if agent is not None else None,
            title=planned.title,
            objective=planned.objective,
            priority=planned.priority,
            status=task_status.value,
            input_data={
                "orchestration_run_id": str(run.id),
                "sequence": sequence,
                "context": context,
                **(
                    {
                        "tool_request": {
                            "slug": planned.tool_slug,
                            "input": planned.tool_input or {},
                        }
                    }
                    if planned.tool_slug
                    else {}
                ),
                "agent_routing": {
                    "mode": "evidence-weighted-v1",
                    "capability_match_score": score,
                    "performance_evidence": (
                        performance_evidence.get(agent.id, {}) if agent is not None else {}
                    ),
                },
            },
        )
        session.add(task)
        session.flush()
        session.add(
            TaskEvent(
                organization_id=organization_id,
                task_id=task.id,
                actor_user_id=created_by_user_id,
                event_type="task.created",
                details={
                    "source": "executive-orchestrator",
                    "orchestration_run_id": str(run.id),
                    "status": task.status,
                    "requires_approval": planned.requires_approval,
                    "tool_slug": planned.tool_slug,
                    "project_id": str(project_id) if project_id else None,
                },
            )
        )
        step = OrchestrationStep(
            orchestration_run_id=run.id,
            organization_id=organization_id,
            task_id=task.id,
            assigned_agent_id=agent.id if agent is not None else None,
            sequence=sequence,
            title=planned.title,
            objective=planned.objective,
            required_capabilities=planned.required_capabilities,
            requires_approval=planned.requires_approval,
            match_score=score,
        )
        session.add(step)
        session.flush()

        if planned.requires_approval:
            approval = OrchestrationApproval(
                organization_id=organization_id,
                orchestration_run_id=run.id,
                orchestration_step_id=step.id,
                status=ApprovalStatus.PENDING.value,
                requested_by_user_id=created_by_user_id,
            )
            session.add(approval)
            session.flush()
            approval_required_steps += 1
            record_audit(
                session,
                organization_id=organization_id,
                actor_user_id=created_by_user_id,
                action="orchestration.approval.requested",
                resource_type="orchestration_approval",
                resource_id=str(approval.id),
                details={
                    "orchestration_run_id": str(run.id),
                    "orchestration_step_id": str(step.id),
                    "sequence": sequence,
                },
            )

        if agent is not None:
            matched_steps += 1

    if matched_steps:
        run.status = OrchestrationStatus.ACTIVE.value
    run.summary = {
        "step_count": len(plan),
        "matched_steps": matched_steps,
        "unmatched_steps": len(plan) - matched_steps,
        "approval_required_steps": approval_required_steps,
        "tool_steps": sum(bool(step.tool_slug) for step in plan),
        "agent_routing": {
            "mode": "evidence-weighted-v1",
            "agents_with_completed_evidence": sum(
                int(item.get("completed_tasks", 0)) > 0
                for item in performance_evidence.values()
            ),
        },
    }
    session.flush()
    return run


def refresh_orchestration_status(session: Session, run: OrchestrationRun) -> OrchestrationRun:
    task_statuses = list(
        session.scalars(
            select(Task.status)
            .join(OrchestrationStep, OrchestrationStep.task_id == Task.id)
            .where(OrchestrationStep.orchestration_run_id == run.id)
        )
    )
    if not task_statuses:
        run.status = OrchestrationStatus.PLANNED.value
        return run

    statuses = [TaskStatus(value) for value in task_statuses]
    terminal = [status for status in statuses if status in TERMINAL_TASK_STATUSES]
    succeeded = statuses.count(TaskStatus.SUCCEEDED)

    if len(terminal) == len(statuses):
        if succeeded == len(statuses):
            run.status = OrchestrationStatus.SUCCEEDED.value
        elif succeeded:
            run.status = OrchestrationStatus.PARTIAL.value
        elif all(status is TaskStatus.CANCELLED for status in statuses):
            run.status = OrchestrationStatus.CANCELLED.value
        else:
            run.status = OrchestrationStatus.FAILED.value
    elif any(status in {TaskStatus.ASSIGNED, TaskStatus.RUNNING} for status in statuses):
        run.status = OrchestrationStatus.ACTIVE.value
    else:
        run.status = OrchestrationStatus.PLANNED.value

    run.summary = {
        **(run.summary or {}),
        "succeeded_steps": succeeded,
        "terminal_steps": len(terminal),
    }
    session.flush()
    return run
