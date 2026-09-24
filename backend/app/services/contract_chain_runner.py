from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.tools import ToolRunStatus, ToolStatus
from backend.app.models.agent import Agent
from backend.app.models.task import Task, TaskEvent
from backend.app.models.tool_definition import ToolDefinition
from backend.app.models.tool_run import ToolRun
from backend.app.services.audit import record_audit
from backend.app.services.tool_gateway import (
    ToolGatewayError,
    approve_tool_run,
    create_tool_run,
    execute_tool_run,
)


CHAIN_RUNNER_VERSION = "contract-chain-v1"


class ContractChainError(RuntimeError):
    pass


def _contract(task: Task) -> dict[str, Any] | None:
    value = (task.input_data or {}).get("compiled_execution_contract")
    return value if isinstance(value, dict) else None


def _clean_model_text(value: str) -> str:
    text = value.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            lines = lines[1:-1]
            text = "\n".join(lines).strip()
    return text


def _model_output(task: Task) -> dict[str, Any] | None:
    output = task.output_data or {}
    structured = output.get("structured_output")
    if isinstance(structured, dict):
        return structured
    text = output.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        parsed = json.loads(_clean_model_text(text))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _path_value(value: Any, path: str) -> tuple[bool, Any]:
    current = value
    if not path:
        return True, current
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _binding_value(
    binding: str,
    *,
    model_output: dict[str, Any] | None,
    step_outputs: dict[str, Any],
    upstream: dict[str, Any],
    repeat_index: int | None,
) -> tuple[bool, Any]:
    parts = binding.split(".")
    if not parts:
        return False, None

    root = parts[0]
    if root == "model":
        current: Any = model_output
        rest = parts[1:]
    elif root == "upstream":
        current = upstream
        rest = parts[1:]
    elif root == "steps" and len(parts) >= 3:
        current = step_outputs.get(parts[1])
        rest = parts[2:]
    else:
        return False, None

    for segment in rest:
        if segment.endswith("[*]"):
            key = segment[:-3]
            if not isinstance(current, dict):
                return False, None
            items = current.get(key)
            if not isinstance(items, list) or repeat_index is None:
                return False, None
            if repeat_index < 0 or repeat_index >= len(items):
                return False, None
            current = items[repeat_index]
            continue
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _model_step_valid(step: dict[str, Any], model_output: dict[str, Any] | None) -> bool:
    if model_output is None:
        return False
    if step.get("id") != "produce-artifacts":
        return True

    artifacts = model_output.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False
    if len(artifacts) > 20:
        return False
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return False
        for field in ("path", "content", "message"):
            if not isinstance(artifact.get(field), str):
                return False
        if not artifact["path"].strip() or not artifact["message"].strip():
            return False
    return isinstance(model_output.get("acceptance_notes"), str)


def _acceptance(
    step: dict[str, Any],
    output: dict[str, Any],
) -> tuple[str, str | None]:
    acceptance = step.get("acceptance")
    if not isinstance(acceptance, dict):
        return "accepted", None

    if acceptance.get("receipt_required"):
        evidence = output.get("evidence")
        if not isinstance(evidence, dict) or not evidence.get("receipt_id"):
            return "rejected", "missing_execution_receipt"

    output_path = acceptance.get("output_path")
    if isinstance(output_path, str) and output_path:
        found, value = _path_value(output, output_path)
        if not found:
            return "rejected", f"acceptance_output_missing:{output_path}"

        pending_values = acceptance.get("pending_values")
        if not isinstance(pending_values, list):
            pending_values = []
        pending_status_path = acceptance.get("pending_status_path")
        pending_status_values = acceptance.get("pending_status_values")
        if isinstance(pending_status_path, str) and isinstance(
            pending_status_values,
            list,
        ):
            pending_found, pending_value = _path_value(output, pending_status_path)
            if pending_found and pending_value in pending_status_values:
                return "pending", "provider_result_pending"
        if value in pending_values:
            return "pending", "provider_result_pending"

        if "equals" in acceptance and value != acceptance["equals"]:
            return "rejected", f"acceptance_mismatch:{output_path}"
        allowed = acceptance.get("in")
        if isinstance(allowed, list) and value not in allowed:
            return "rejected", f"acceptance_not_allowed:{output_path}"

    return "accepted", None


def _receipt(run: ToolRun) -> str:
    output = run.output_data or {}
    evidence = output.get("evidence") if isinstance(output, dict) else None
    if isinstance(evidence, dict) and evidence.get("receipt_id"):
        return str(evidence["receipt_id"])
    return f"tool-run:{run.id}"


def _tool_for_step(
    session: Session,
    *,
    task: Task,
    step: dict[str, Any],
) -> ToolDefinition | None:
    raw_id = step.get("tool_id")
    tool: ToolDefinition | None = None
    if raw_id:
        try:
            tool = session.get(ToolDefinition, UUID(str(raw_id)))
        except ValueError:
            tool = None
    if tool is None and step.get("tool_slug"):
        tool = session.scalar(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == task.organization_id,
                ToolDefinition.slug == str(step["tool_slug"]),
            )
        )
    if tool is None or tool.organization_id != task.organization_id:
        return None
    if tool.status != ToolStatus.ACTIVE.value:
        return None
    if tool.provider != step.get("provider") or tool.action_name != step.get("action_name"):
        return None
    return tool


def _state(task: Task, contract: dict[str, Any]) -> dict[str, Any]:
    output = task.output_data or {}
    existing = output.get("contract_execution")
    if (
        isinstance(existing, dict)
        and existing.get("contract_version") == contract.get("version")
    ):
        return dict(existing)
    return {
        "version": CHAIN_RUNNER_VERSION,
        "contract_version": contract.get("version"),
        "status": "not_started",
        "current_step_id": None,
        "steps": {},
        "evidence_refs": [],
        "halted_reason": None,
    }


def _persist(
    session: Session,
    *,
    task: Task,
    state: dict[str, Any],
    actor_user_id: UUID,
    event_type: str,
) -> None:
    output = dict(task.output_data or {})
    output["contract_execution"] = state
    task.output_data = output
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=task.assigned_agent_id,
            event_type=event_type,
            details={
                "chain_version": CHAIN_RUNNER_VERSION,
                "status": state.get("status"),
                "current_step_id": state.get("current_step_id"),
                "halted_reason": state.get("halted_reason"),
            },
        )
    )
    session.commit()
    session.refresh(task)


def _runtime_input(
    step: dict[str, Any],
    *,
    model_output: dict[str, Any] | None,
    step_outputs: dict[str, Any],
    upstream: dict[str, Any],
    repeat_index: int | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    resolved = dict(step.get("input") or {})
    unresolved: list[str] = []
    bindings = step.get("bindings")
    if not isinstance(bindings, dict):
        bindings = {}

    for field, binding in bindings.items():
        if not isinstance(binding, str):
            unresolved.append(str(field))
            continue
        found, value = _binding_value(
            binding,
            model_output=model_output,
            step_outputs=step_outputs,
            upstream=upstream,
            repeat_index=repeat_index,
        )
        if not found or value is None:
            unresolved.append(str(field))
            continue
        resolved[str(field)] = value

    if unresolved:
        return None, unresolved
    return resolved, []


def _repeat_count(
    step: dict[str, Any],
    model_output: dict[str, Any] | None,
) -> int:
    acceptance = step.get("acceptance")
    if not isinstance(acceptance, dict):
        return 1
    repeat = acceptance.get("repeat_for_each")
    if repeat != "model.artifacts":
        return 1
    artifacts = model_output.get("artifacts") if model_output else None
    return len(artifacts) if isinstance(artifacts, list) else 0


def _existing_run(
    session: Session,
    *,
    task: Task,
    tool: ToolDefinition,
    step_id: str,
    repeat_index: int,
) -> ToolRun | None:
    marker = {
        "step_id": step_id,
        "repeat_index": repeat_index,
    }
    runs = session.scalars(
        select(ToolRun)
        .where(
            ToolRun.organization_id == task.organization_id,
            ToolRun.task_id == task.id,
            ToolRun.tool_id == tool.id,
        )
        .order_by(ToolRun.requested_at.desc())
    )
    for run in runs:
        if (run.input_data or {}).get("_seldrune_contract") == marker:
            return run
    return None


def _execute_tool_step(
    session: Session,
    *,
    task: Task,
    agent: Agent | None,
    actor_user_id: UUID,
    step: dict[str, Any],
    model_output: dict[str, Any] | None,
    step_outputs: dict[str, Any],
    upstream: dict[str, Any],
    confirmed_sensitive_action: bool,
) -> tuple[str, str | None, list[dict[str, Any]], list[str]]:
    tool = _tool_for_step(session, task=task, step=step)
    if tool is None:
        return "blocked", "compiled_tool_unavailable", [], []
    if (
        agent is not None
        and agent.allowed_tool_slugs is not None
        and tool.slug not in agent.allowed_tool_slugs
    ):
        return "blocked", "compiled_tool_not_allowed_for_agent", [], []

    count = _repeat_count(step, model_output)
    if count < 1:
        return "blocked", "repeat_source_unresolved", [], []

    records: list[dict[str, Any]] = []
    receipts: list[str] = []
    for index in range(count):
        resolved_input, unresolved = _runtime_input(
            step,
            model_output=model_output,
            step_outputs=step_outputs,
            upstream=upstream,
            repeat_index=index if count > 1 else None,
        )
        if resolved_input is None:
            return (
                "blocked",
                "runtime_binding_unresolved:" + ",".join(unresolved),
                records,
                receipts,
            )

        marker = {"step_id": str(step["id"]), "repeat_index": index}
        tool_input = {
            **resolved_input,
            "_seldrune_contract": marker,
        }
        run = _existing_run(
            session,
            task=task,
            tool=tool,
            step_id=str(step["id"]),
            repeat_index=index,
        )
        if run is None:
            try:
                run = create_tool_run(
                    session,
                    tool=tool,
                    organization_id=task.organization_id,
                    requested_by_user_id=actor_user_id,
                    input_data=tool_input,
                    task_id=task.id,
                    agent_id=agent.id if agent is not None else None,
                )
            except ToolGatewayError as exc:
                return "failed", f"tool_run_create_failed:{exc}", records, receipts

        if (
            run.status == ToolRunStatus.PENDING_APPROVAL.value
            and confirmed_sensitive_action
        ):
            try:
                run = approve_tool_run(
                    session,
                    run=run,
                    actor_user_id=actor_user_id,
                )
            except ToolGatewayError as exc:
                return "failed", f"tool_approval_failed:{exc}", records, receipts

        if run.status == ToolRunStatus.PENDING_APPROVAL.value:
            records.append(
                {
                    "repeat_index": index,
                    "tool_run_id": str(run.id),
                    "status": run.status,
                }
            )
            return "blocked", "tool_approval_required", records, receipts

        if run.status == ToolRunStatus.APPROVED.value:
            try:
                run = execute_tool_run(
                    session,
                    run=run,
                    tool=tool,
                    actor_user_id=actor_user_id,
                )
            except ToolGatewayError as exc:
                return "failed", f"tool_execution_failed:{exc}", records, receipts

        if run.status == ToolRunStatus.RUNNING.value:
            records.append(
                {
                    "repeat_index": index,
                    "tool_run_id": str(run.id),
                    "status": run.status,
                }
            )
            return "pending", "tool_run_in_progress", records, receipts

        if run.status != ToolRunStatus.SUCCEEDED.value:
            records.append(
                {
                    "repeat_index": index,
                    "tool_run_id": str(run.id),
                    "status": run.status,
                    "error": run.error_message,
                }
            )
            return "failed", f"tool_run_{run.status}", records, receipts

        run_output = run.output_data or {}
        acceptance_status, acceptance_reason = _acceptance(step, run_output)
        receipt = _receipt(run)
        records.append(
            {
                "repeat_index": index,
                "tool_run_id": str(run.id),
                "status": run.status,
                "receipt_id": receipt,
                "output": run_output,
                "acceptance_status": acceptance_status,
                "acceptance_reason": acceptance_reason,
            }
        )
        receipts.append(receipt)

        if acceptance_status == "pending":
            return "pending", acceptance_reason, records, receipts
        if acceptance_status != "accepted":
            return "failed", acceptance_reason, records, receipts

    return "accepted", None, records, receipts


def run_compiled_execution_contract(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID,
    confirmed_sensitive_action: bool = False,
) -> dict[str, Any]:
    contract = _contract(task)
    if contract is None:
        raise ContractChainError("Task has no compiled execution contract")

    state = _state(task, contract)
    model_output = _model_output(task)
    upstream = (task.input_data or {}).get("contract_runtime_context") or {}
    if not isinstance(upstream, dict):
        upstream = {}
    agent = (
        session.get(Agent, task.assigned_agent_id)
        if task.assigned_agent_id is not None
        else None
    )
    if agent is not None and agent.organization_id != task.organization_id:
        agent = None

    step_outputs: dict[str, Any] = {}
    evidence_refs: list[str] = []
    steps_state: dict[str, Any] = {}
    existing_steps = state.get("steps")
    if isinstance(existing_steps, dict):
        steps_state = dict(existing_steps)

    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="cognitive_mission.contract_chain.started",
        resource_type="task",
        resource_id=str(task.id),
        details={
            "chain_version": CHAIN_RUNNER_VERSION,
            "contract_version": contract.get("version"),
        },
    )
    session.commit()

    tool_steps_seen = 0
    for step in contract.get("steps") or []:
        if not isinstance(step, dict) or not step.get("id"):
            state["status"] = "failed"
            state["halted_reason"] = "invalid_compiled_step"
            break

        step_id = str(step["id"])
        state["current_step_id"] = step_id
        kind = str(step.get("kind") or "")

        if kind == "model":
            if not _model_step_valid(step, model_output):
                state["status"] = "waiting"
                state["halted_reason"] = f"model_output_required:{step_id}"
                steps_state[step_id] = {
                    "status": "waiting",
                    "reason": "structured_model_output_required",
                }
                break
            steps_state[step_id] = {
                "status": "accepted_as_input",
                "completion_evidence": False,
            }
            step_outputs[step_id] = model_output
            continue

        if kind != "tool":
            state["status"] = "failed"
            state["halted_reason"] = f"unsupported_step_kind:{kind}"
            break

        tool_steps_seen += 1
        status, reason, records, receipts = _execute_tool_step(
            session,
            task=task,
            agent=agent,
            actor_user_id=actor_user_id,
            step=step,
            model_output=model_output,
            step_outputs=step_outputs,
            upstream=upstream,
            confirmed_sensitive_action=confirmed_sensitive_action,
        )
        steps_state[step_id] = {
            "status": status,
            "reason": reason,
            "runs": records,
        }
        accepted_outputs = [
            item.get("output")
            for item in records
            if item.get("acceptance_status") == "accepted"
            and isinstance(item.get("output"), dict)
        ]
        if len(accepted_outputs) == 1:
            step_outputs[step_id] = accepted_outputs[0]
        elif accepted_outputs:
            step_outputs[step_id] = {"items": accepted_outputs}
        evidence_refs.extend(f"receipt:{value}" for value in receipts)

        if status != "accepted":
            state["status"] = "blocked" if status in {"blocked", "pending"} else "failed"
            state["halted_reason"] = reason
            break
    else:
        if tool_steps_seen < 1:
            state["status"] = "waiting"
            state["halted_reason"] = "independent_machine_evidence_required"
        else:
            state["status"] = "verified"
            state["halted_reason"] = None
            state["current_step_id"] = None

    state["steps"] = steps_state
    state["evidence_refs"] = sorted(set(evidence_refs))
    _persist(
        session,
        task=task,
        state=state,
        actor_user_id=actor_user_id,
        event_type="cognitive_mission.contract_chain.updated",
    )
    return state


def verify_persisted_contract_chain(
    session: Session,
    *,
    task: Task,
) -> tuple[bool, str, list[str]]:
    contract = _contract(task)
    output = task.output_data or {}
    state = output.get("contract_execution")
    if contract is None:
        return False, "compiled_contract_missing", []
    if not isinstance(state, dict) or state.get("status") != "verified":
        reason = (
            str(state.get("halted_reason"))
            if isinstance(state, dict) and state.get("halted_reason")
            else "compiled_contract_not_verified"
        )
        return False, reason, []

    steps_state = state.get("steps")
    if not isinstance(steps_state, dict):
        return False, "compiled_chain_state_missing", []

    evidence_refs: list[str] = []
    tool_steps = [
        step
        for step in contract.get("steps") or []
        if isinstance(step, dict) and step.get("kind") == "tool"
    ]
    if not tool_steps:
        return False, "compiled_contract_has_no_machine_evidence", []

    for step in tool_steps:
        step_id = str(step.get("id") or "")
        persisted = steps_state.get(step_id)
        if not isinstance(persisted, dict) or persisted.get("status") != "accepted":
            return False, f"compiled_step_not_accepted:{step_id}", []
        runs = persisted.get("runs")
        if not isinstance(runs, list) or not runs:
            return False, f"compiled_step_runs_missing:{step_id}", []

        expected_tool = _tool_for_step(session, task=task, step=step)
        if expected_tool is None:
            return False, f"compiled_tool_unavailable:{step_id}", []

        for record in runs:
            if not isinstance(record, dict) or not record.get("tool_run_id"):
                return False, f"compiled_run_reference_missing:{step_id}", []
            try:
                run_id = UUID(str(record["tool_run_id"]))
            except ValueError:
                return False, f"compiled_run_reference_invalid:{step_id}", []
            run = session.get(ToolRun, run_id)
            if run is None:
                return False, f"compiled_run_missing:{step_id}", []
            if run.organization_id != task.organization_id or run.task_id != task.id:
                return False, f"compiled_run_scope_mismatch:{step_id}", []
            if run.tool_id != expected_tool.id:
                return False, f"compiled_run_tool_mismatch:{step_id}", []
            if run.status != ToolRunStatus.SUCCEEDED.value:
                return False, f"compiled_run_not_succeeded:{step_id}", []

            acceptance_status, reason = _acceptance(step, run.output_data or {})
            if acceptance_status != "accepted":
                return False, reason or f"compiled_acceptance_failed:{step_id}", []
            evidence_refs.append(f"receipt:{_receipt(run)}")

    return True, "verified_compiled_contract_chain", sorted(set(evidence_refs))
