from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.tasking import AgentStatus, TaskStatus
from backend.app.core.tools import ToolRunStatus
from backend.app.models.agent import Agent
from backend.app.models.governance_policy import GovernancePolicy
from backend.app.models.task import Task, TaskEvent
from backend.app.models.tool_run import ToolRun
from backend.app.services.agent_runtime import AgentRuntimeError, execute_agent_task
from backend.app.services.audit import record_audit
from backend.app.services.autonomous_execution import _execute_registered_tool
from backend.app.services.contract_chain_runner import (
    run_compiled_execution_contract,
    verify_persisted_contract_chain,
)
from backend.app.services.development_mission import (
    MISSION_KIND,
    queue_parallel_ready_stages,
    sync_development_mission_task,
)
from backend.app.services.model_gateway import ModelGateway
from backend.app.services.orchestrator import (
    build_agent_performance_evidence,
    select_best_agent,
)
from backend.app.services.task_engine import transition_task


CONTROLLER_VERSION = "one-go-v1"


def _stage_id(task: Task) -> str | None:
    value = (task.input_data or {}).get("cognitive_mission_stage_id")
    return str(value) if value else None


def _master_id(task: Task) -> str | None:
    value = (task.input_data or {}).get("master_mission_task_id")
    return str(value) if value else None


def _mission_tasks(
    session: Session,
    *,
    organization_id: UUID,
    master_task_id: UUID,
) -> list[Task]:
    return [
        task
        for task in session.scalars(
            select(Task)
            .where(Task.organization_id == organization_id)
            .order_by(Task.created_at, Task.id)
        )
        if _master_id(task) == str(master_task_id) and _stage_id(task)
    ]


def _verification_from_output(
    session: Session,
    task: Task,
) -> tuple[bool, str, list[str]]:
    output = task.output_data or {}
    if not isinstance(output, dict):
        return False, "missing_structured_output", []

    contract = (task.input_data or {}).get("compiled_execution_contract")
    if isinstance(contract, dict):
        return verify_persisted_contract_chain(session, task=task)

    tool_request = (task.input_data or {}).get("tool_request")
    if not (
        isinstance(tool_request, dict)
        and tool_request.get("slug")
    ):
        return False, "task_has_no_verifiable_tool_contract", []

    evidence = output.get("evidence")
    if not (
        output.get("execution_type") == "tool"
        and isinstance(evidence, dict)
        and evidence.get("receipt_id")
        and evidence.get("tool_run_id")
    ):
        return False, "model_output_is_not_completion_evidence", []

    expected_tool_slug = str(tool_request["slug"])
    if str(output.get("tool_slug") or "") != expected_tool_slug:
        return False, "tool_contract_mismatch", []

    try:
        tool_run_id = UUID(str(evidence["tool_run_id"]))
    except (TypeError, ValueError):
        return False, "invalid_tool_run_reference", []

    tool_run = session.get(ToolRun, tool_run_id)
    if tool_run is None:
        return False, "tool_run_not_found", []
    if tool_run.organization_id != task.organization_id:
        return False, "tool_run_wrong_organization", []
    if tool_run.task_id != task.id:
        return False, "tool_run_wrong_task", []
    if tool_run.status != ToolRunStatus.SUCCEEDED.value:
        return False, "tool_run_not_succeeded", []

    run_output = tool_run.output_data or {}
    provider_evidence = (
        run_output.get("evidence")
        if isinstance(run_output, dict)
        else None
    )
    expected_receipt = (
        str(provider_evidence.get("receipt_id"))
        if isinstance(provider_evidence, dict)
        and provider_evidence.get("receipt_id")
        else f"tool-run:{tool_run.id}"
    )
    receipt_id = str(evidence["receipt_id"])
    if receipt_id != expected_receipt:
        return False, "tool_receipt_mismatch", []

    return True, "verified_tool_receipt", [
        f"receipt:{receipt_id}",
        f"tool-run:{tool_run.id}",
    ]


def _record_verification(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID,
) -> tuple[bool, str, list[str]]:
    output = dict(task.output_data or {})
    existing = output.get("cognitive_verification")
    if isinstance(existing, dict) and existing.get("status") == "verified":
        refs = existing.get("evidence_refs")
        return True, "already_verified", [
            str(item) for item in refs if item
        ] if isinstance(refs, list) else []

    verified, reason, refs = _verification_from_output(session, task)
    output["cognitive_verification"] = {
        "status": "verified" if verified else "unverified",
        "reason": reason,
        "evidence_refs": refs,
        "controller_version": CONTROLLER_VERSION,
    }
    task.output_data = output
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=task.assigned_agent_id,
            event_type=(
                "cognitive_mission.stage_verified"
                if verified
                else "cognitive_mission.stage_unverified"
            ),
            details={
                "stage_id": _stage_id(task),
                "reason": reason,
                "evidence_refs": refs,
            },
        )
    )
    session.commit()
    session.refresh(task)
    return verified, reason, refs


def _assign_best_agent(
    session: Session,
    *,
    task: Task,
    agents: list[Agent],
    performance: dict[UUID, dict[str, float | int]],
    actor_user_id: UUID,
) -> tuple[Agent | None, int]:
    if task.assigned_agent_id is not None:
        agent = session.get(Agent, task.assigned_agent_id)
        if (
            agent is not None
            and agent.organization_id == task.organization_id
            and agent.status == AgentStatus.ACTIVE.value
        ):
            return agent, 100

    required = (task.input_data or {}).get("required_capabilities") or []
    required_capabilities = [
        str(item) for item in required if isinstance(item, str) and item.strip()
    ]
    tool_request = (task.input_data or {}).get("tool_request")
    required_tool_slug = (
        str(tool_request.get("slug"))
        if isinstance(tool_request, dict) and tool_request.get("slug")
        else None
    )
    agent, score = select_best_agent(
        agents,
        required_capabilities,
        performance,
        required_tool_slug,
    )
    if agent is None:
        return None, score

    task.assigned_agent_id = agent.id
    if TaskStatus(task.status) is TaskStatus.QUEUED:
        transition_task(task, TaskStatus.ASSIGNED)
    task.input_data = {
        **(task.input_data or {}),
        "one_go_routing": {
            "controller_version": CONTROLLER_VERSION,
            "agent_id": str(agent.id),
            "capability_match_score": score,
            "performance_evidence": performance.get(agent.id, {}),
        },
    }
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="cognitive_mission.stage_assigned",
            details={
                "stage_id": _stage_id(task),
                "capability_match_score": score,
            },
        )
    )
    session.commit()
    session.refresh(task)
    return agent, score


def _stage_result(
    task: Task,
    *,
    disposition: str,
    reason: str | None = None,
    match_score: int | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    contract = (task.input_data or {}).get("compiled_execution_contract")
    compiler = contract if isinstance(contract, dict) else {}
    execution = (task.output_data or {}).get("contract_execution")
    chain = execution if isinstance(execution, dict) else {}
    return {
        "task_id": str(task.id),
        "stage_id": _stage_id(task),
        "task_status": task.status,
        "disposition": disposition,
        "reason": reason,
        "assigned_agent_id": (
            str(task.assigned_agent_id) if task.assigned_agent_id else None
        ),
        "match_score": match_score,
        "evidence_refs": evidence_refs or [],
        "compiled_contract_version": compiler.get("version"),
        "compiled_profile": compiler.get("profile"),
        "compiled_executable_now": compiler.get("executable_now"),
        "compiled_blocking_reasons": compiler.get("blocking_reasons") or [],
        "contract_chain_version": chain.get("version"),
        "contract_chain_status": chain.get("status"),
        "contract_chain_halted_reason": chain.get("halted_reason"),
    }


def execute_one_go_controller(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    max_waves: int = 3,
    max_tasks: int = 8,
    gateway: ModelGateway | None = None,
) -> dict[str, Any]:
    if not 1 <= max_waves <= 10:
        raise ValueError("max_waves must be between 1 and 10")
    if not 1 <= max_tasks <= 50:
        raise ValueError("max_tasks must be between 1 and 50")

    master_task, mission, _ = sync_development_mission_task(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    policy = session.get(GovernancePolicy, organization_id)
    governance_allowed = (
        policy is None or bool(policy.allow_autonomous_execution)
    )
    effective_task_limit = min(
        max_tasks,
        policy.max_steps_per_command if policy is not None else max_tasks,
    )
    queue_parallel_ready_stages(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        master_task=master_task,
    )

    agents = list(
        session.scalars(
            select(Agent).where(
                Agent.organization_id == organization_id,
                Agent.status == AgentStatus.ACTIVE.value,
            )
        )
    )
    performance = build_agent_performance_evidence(
        session,
        organization_id=organization_id,
        agents=agents,
    )

    report: dict[str, Any] = {
        "controller_version": CONTROLLER_VERSION,
        "mission_kind": MISSION_KIND,
        "master_task_id": str(master_task.id),
        "starting_percentage": mission["overall_percentage"],
        "ending_percentage": mission["overall_percentage"],
        "waves_requested": max_waves,
        "waves_executed": 0,
        "task_limit_requested": max_tasks,
        "task_limit": effective_task_limit,
        "governance": {
            "autonomous_execution_allowed": governance_allowed,
            "max_steps_per_command": (
                policy.max_steps_per_command if policy is not None else None
            ),
        },
        "tasks_considered": 0,
        "tasks_executed": 0,
        "tasks_verified": 0,
        "tasks_unverified": 0,
        "tasks_blocked": 0,
        "tasks_failed": 0,
        "stage_results": [],
        "halted_reason": None,
    }

    effective_max_waves = max_waves
    if not governance_allowed:
        effective_max_waves = 0
        report["halted_reason"] = "governance_autonomous_execution_disabled"

    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="cognitive_mission.one_go.started",
        resource_type="task",
        resource_id=str(master_task.id),
        details={
            "controller_version": CONTROLLER_VERSION,
            "max_waves": max_waves,
            "max_tasks": max_tasks,
        },
    )
    session.commit()

    previously_ready: set[str] | None = None
    for _wave_number in range(1, effective_max_waves + 1):
        master_task, mission, _ = sync_development_mission_task(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
        )
        queue_parallel_ready_stages(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            master_task=master_task,
        )
        ready_ids = set(mission["parallel_ready_stage_ids"])
        if not ready_ids:
            report["halted_reason"] = "no_ready_stages"
            break
        if previously_ready is not None and ready_ids == previously_ready:
            report["halted_reason"] = "no_new_verified_dependency_progress"
            break

        ready_order = {
            stage_id: index
            for index, stage_id in enumerate(mission["parallel_ready_stage_ids"])
        }
        wave_tasks = sorted(
            (
                task
                for task in _mission_tasks(
                    session,
                    organization_id=organization_id,
                    master_task_id=master_task.id,
                )
                if _stage_id(task) in ready_ids
            ),
            key=lambda task: ready_order.get(_stage_id(task) or "", 10_000),
        )
        if not wave_tasks:
            report["halted_reason"] = "ready_tasks_missing"
            break

        report["waves_executed"] += 1
        wave_verified = 0
        for task in wave_tasks:
            if report["tasks_considered"] >= effective_task_limit:
                report["halted_reason"] = "task_limit"
                break
            report["tasks_considered"] += 1

            execution_mode = str(
                (task.input_data or {}).get("execution_mode", "automatic")
            )
            if execution_mode in {"owner-gated", "external-resource"}:
                report["tasks_blocked"] += 1
                report["stage_results"].append(
                    _stage_result(
                        task,
                        disposition="blocked",
                        reason=f"{execution_mode}_requires_explicit_execution",
                    )
                )
                continue

            task_status = TaskStatus(task.status)
            if task_status is TaskStatus.SUCCEEDED:
                contract = (task.input_data or {}).get("compiled_execution_contract")
                if isinstance(contract, dict):
                    chain = run_compiled_execution_contract(
                        session,
                        task=task,
                        actor_user_id=actor_user_id,
                        confirmed_sensitive_action=False,
                    )
                    if chain["status"] == "failed":
                        report["tasks_failed"] += 1
                        report["stage_results"].append(
                            _stage_result(
                                task,
                                disposition="failed",
                                reason=chain.get("halted_reason"),
                            )
                        )
                        continue
                    if chain["status"] == "blocked":
                        report["tasks_blocked"] += 1
                        report["stage_results"].append(
                            _stage_result(
                                task,
                                disposition="blocked",
                                reason=chain.get("halted_reason"),
                            )
                        )
                        continue
                verified, reason, refs = _record_verification(
                    session,
                    task=task,
                    actor_user_id=actor_user_id,
                )
                if verified:
                    report["tasks_verified"] += 1
                    wave_verified += 1
                    disposition = "verified"
                else:
                    report["tasks_unverified"] += 1
                    disposition = "unverified"
                report["stage_results"].append(
                    _stage_result(
                        task,
                        disposition=disposition,
                        reason=reason,
                        evidence_refs=refs,
                    )
                )
                continue

            if task_status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
                report["tasks_failed"] += 1
                report["stage_results"].append(
                    _stage_result(
                        task,
                        disposition="failed",
                        reason=f"task_{task_status.value}",
                    )
                )
                continue

            agent, match_score = _assign_best_agent(
                session,
                task=task,
                agents=agents,
                performance=performance,
                actor_user_id=actor_user_id,
            )
            if agent is None:
                report["tasks_blocked"] += 1
                report["stage_results"].append(
                    _stage_result(
                        task,
                        disposition="blocked",
                        reason="no_capable_active_agent",
                        match_score=match_score,
                    )
                )
                continue

            tool_request = (task.input_data or {}).get("tool_request")
            if isinstance(tool_request, dict):
                tool_status, tool_reason = _execute_registered_tool(
                    session,
                    task=task,
                    agent=agent,
                    actor_user_id=actor_user_id,
                    confirmed_sensitive_action=False,
                )
                if tool_status == "approval_required":
                    report["tasks_blocked"] += 1
                    report["stage_results"].append(
                        _stage_result(
                            task,
                            disposition="blocked",
                            reason=tool_reason,
                            match_score=match_score,
                        )
                    )
                    continue
                if tool_status not in {"succeeded", "not_applicable"}:
                    if tool_status == "blocked":
                        report["tasks_blocked"] += 1
                        disposition = "blocked"
                    else:
                        report["tasks_failed"] += 1
                        disposition = "failed"
                    report["stage_results"].append(
                        _stage_result(
                            task,
                            disposition=disposition,
                            reason=tool_reason,
                            match_score=match_score,
                        )
                    )
                    continue

            if TaskStatus(task.status) is TaskStatus.ASSIGNED:
                try:
                    execute_agent_task(
                        session,
                        task=task,
                        agent=agent,
                        actor_user_id=actor_user_id,
                        gateway=gateway,
                    )
                    report["tasks_executed"] += 1
                except AgentRuntimeError as exc:
                    report["tasks_failed"] += 1
                    report["stage_results"].append(
                        _stage_result(
                            task,
                            disposition="failed",
                            reason=str(exc),
                            match_score=match_score,
                        )
                    )
                    continue
            elif TaskStatus(task.status) is TaskStatus.SUCCEEDED:
                report["tasks_executed"] += 1
            else:
                report["tasks_blocked"] += 1
                report["stage_results"].append(
                    _stage_result(
                        task,
                        disposition="blocked",
                        reason=f"unsupported_task_status:{task.status}",
                        match_score=match_score,
                    )
                )
                continue

            contract = (task.input_data or {}).get("compiled_execution_contract")
            if isinstance(contract, dict):
                chain = run_compiled_execution_contract(
                    session,
                    task=task,
                    actor_user_id=actor_user_id,
                    confirmed_sensitive_action=False,
                )
                if chain["status"] == "failed":
                    report["tasks_failed"] += 1
                    report["stage_results"].append(
                        _stage_result(
                            task,
                            disposition="failed",
                            reason=chain.get("halted_reason"),
                            match_score=match_score,
                        )
                    )
                    continue
                if chain["status"] == "blocked":
                    report["tasks_blocked"] += 1
                    report["stage_results"].append(
                        _stage_result(
                            task,
                            disposition="blocked",
                            reason=chain.get("halted_reason"),
                            match_score=match_score,
                        )
                    )
                    continue

            verified, reason, refs = _record_verification(
                session,
                task=task,
                actor_user_id=actor_user_id,
            )
            if verified:
                report["tasks_verified"] += 1
                wave_verified += 1
                disposition = "verified"
            else:
                report["tasks_unverified"] += 1
                disposition = "unverified"
            report["stage_results"].append(
                _stage_result(
                    task,
                    disposition=disposition,
                    reason=reason,
                    match_score=match_score,
                    evidence_refs=refs,
                )
            )

        master_task, updated_mission, _ = sync_development_mission_task(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
        )
        report["ending_percentage"] = updated_mission["overall_percentage"]
        updated_ready = set(updated_mission["parallel_ready_stage_ids"])

        if report["halted_reason"] == "task_limit":
            break
        if wave_verified == 0 or updated_ready == ready_ids:
            report["halted_reason"] = "no_new_verified_dependency_progress"
            break
        previously_ready = ready_ids

    master_output = dict(master_task.output_data or {})
    master_output["one_go_execution"] = report
    master_task.output_data = master_output
    session.add(
        TaskEvent(
            organization_id=organization_id,
            task_id=master_task.id,
            actor_user_id=actor_user_id,
            event_type="cognitive_mission.one_go.completed",
            details={
                "controller_version": CONTROLLER_VERSION,
                "waves_executed": report["waves_executed"],
                "tasks_executed": report["tasks_executed"],
                "tasks_verified": report["tasks_verified"],
                "tasks_unverified": report["tasks_unverified"],
                "tasks_blocked": report["tasks_blocked"],
                "tasks_failed": report["tasks_failed"],
                "ending_percentage": report["ending_percentage"],
                "halted_reason": report["halted_reason"],
            },
        )
    )
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="cognitive_mission.one_go.completed",
        resource_type="task",
        resource_id=str(master_task.id),
        details={
            key: report[key]
            for key in (
                "controller_version",
                "waves_executed",
                "tasks_executed",
                "tasks_verified",
                "tasks_unverified",
                "tasks_blocked",
                "tasks_failed",
                "ending_percentage",
                "halted_reason",
            )
        },
    )
    session.commit()
    session.refresh(master_task)
    return report
