from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.tasking import AgentStatus, TaskStatus
from backend.app.core.tools import ToolRunStatus
from backend.app.models.agent import Agent
from backend.app.models.task import Task, TaskEvent
from backend.app.models.tool_run import ToolRun
from backend.app.services.agent_runtime import AgentRuntimeError, execute_agent_task
from backend.app.services.audit import record_audit
from backend.app.services.autonomous_execution import _execute_registered_tool
from backend.app.services.model_gateway import ModelGateway
from backend.app.services.orchestrator import (
    build_agent_performance_evidence,
    select_best_agent,
)
from backend.app.services.task_engine import transition_task


RUNNER_VERSION = "contract-runner-v1"
MAX_ARTIFACTS = 20
MAX_ARTIFACT_CONTENT_CHARS = 300_000
MAX_TOTAL_ARTIFACT_CONTENT_CHARS = 1_000_000
_RETRY_SAFE_READ_ACTIONS = {
    ("github", "repository-info"),
    ("github", "workflow-run-status"),
    ("render", "deploy-status"),
}


class ContractRunnerError(RuntimeError):
    pass


def _contract(task: Task) -> dict[str, Any]:
    raw = (task.input_data or {}).get("compiled_execution_contract")
    if not isinstance(raw, dict):
        raise ContractRunnerError("Task has no compiled execution contract")
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ContractRunnerError("Compiled execution contract has no steps")
    return raw


def _stage_id(task: Task) -> str | None:
    value = (task.input_data or {}).get("cognitive_mission_stage_id")
    return str(value) if value else None


def _child_tasks(
    session: Session,
    *,
    parent_task: Task,
) -> list[Task]:
    return [
        task
        for task in session.scalars(
            select(Task)
            .where(Task.organization_id == parent_task.organization_id)
            .order_by(Task.created_at, Task.id)
        )
        if (task.input_data or {}).get("contract_parent_task_id")
        == str(parent_task.id)
    ]


def _child_step_id(task: Task) -> str | None:
    value = (task.input_data or {}).get("contract_step_id")
    return str(value) if value else None


def _child_repeat_index(task: Task) -> int | None:
    value = (task.input_data or {}).get("contract_repeat_index")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _child_attempt(task: Task) -> int:
    value = (task.input_data or {}).get("contract_step_attempt", 1)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _matching_children(
    children: list[Task],
    *,
    step_id: str,
    repeat_index: int | None,
) -> list[Task]:
    return [
        child
        for child in children
        if _child_step_id(child) == step_id
        and _child_repeat_index(child) == repeat_index
    ]


def _latest_child(
    children: list[Task],
    *,
    step_id: str,
    repeat_index: int | None = None,
) -> Task | None:
    matches = _matching_children(
        children,
        step_id=step_id,
        repeat_index=repeat_index,
    )
    if not matches:
        return None
    return max(matches, key=lambda task: (_child_attempt(task), task.created_at, task.id))


def _assign_parent_agent(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID,
) -> tuple[Agent | None, int]:
    if task.assigned_agent_id is not None:
        assigned = session.get(Agent, task.assigned_agent_id)
        if (
            assigned is not None
            and assigned.organization_id == task.organization_id
            and assigned.status == AgentStatus.ACTIVE.value
        ):
            if TaskStatus(task.status) is TaskStatus.QUEUED:
                transition_task(task, TaskStatus.ASSIGNED)
                session.commit()
                session.refresh(task)
            return assigned, 100

    agents = list(
        session.scalars(
            select(Agent).where(
                Agent.organization_id == task.organization_id,
                Agent.status == AgentStatus.ACTIVE.value,
            )
        )
    )
    performance = build_agent_performance_evidence(
        session,
        organization_id=task.organization_id,
        agents=agents,
    )
    required = [
        str(item)
        for item in (task.input_data or {}).get("required_capabilities") or []
        if isinstance(item, str) and item.strip()
    ]
    agent, score = select_best_agent(
        agents,
        required,
        performance,
        None,
    )
    if agent is None:
        return None, score

    task.assigned_agent_id = agent.id
    if TaskStatus(task.status) is TaskStatus.QUEUED:
        transition_task(task, TaskStatus.ASSIGNED)
    task.input_data = {
        **(task.input_data or {}),
        "contract_routing": {
            "runner_version": RUNNER_VERSION,
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
            event_type="compiled_contract.agent_assigned",
            details={
                "stage_id": _stage_id(task),
                "capability_match_score": score,
            },
        )
    )
    session.commit()
    session.refresh(task)
    return agent, score


def _new_child_task(
    session: Session,
    *,
    parent_task: Task,
    agent: Agent,
    actor_user_id: UUID,
    step: dict[str, Any],
    repeat_index: int | None = None,
    tool_input: dict[str, Any] | None = None,
) -> Task:
    step_id = str(step["id"])
    existing = _child_tasks(session, parent_task=parent_task)
    prior = _matching_children(
        existing,
        step_id=step_id,
        repeat_index=repeat_index,
    )
    attempt = max((_child_attempt(item) for item in prior), default=0) + 1
    kind = str(step.get("kind") or "")
    input_data: dict[str, Any] = {
        "contract_parent_task_id": str(parent_task.id),
        "contract_step_id": step_id,
        "contract_step_attempt": attempt,
        "contract_repeat_index": repeat_index,
        "compiled_contract_version": (
            (parent_task.input_data or {})
            .get("compiled_execution_contract", {})
            .get("version")
        ),
        "cognitive_mission_stage_id": _stage_id(parent_task),
        "evidence_gate_required": True,
    }
    if kind == "model":
        response_schema = step.get("response_schema")
        if isinstance(response_schema, dict):
            input_data["model_response_schema"] = response_schema
        input_data["compiled_stage_context"] = {
            "stage_id": _stage_id(parent_task),
            "stage_title": parent_task.title,
            "parent_objective": parent_task.objective,
            "artifact_limits": {
                "max_artifacts": MAX_ARTIFACTS,
                "max_content_chars_per_artifact": MAX_ARTIFACT_CONTENT_CHARS,
                "max_total_content_chars": MAX_TOTAL_ARTIFACT_CONTENT_CHARS,
            },
        }
    elif kind == "tool":
        tool_slug = step.get("tool_slug")
        if not isinstance(tool_slug, str) or not tool_slug:
            raise ContractRunnerError(f"Compiled tool unavailable for step {step_id}")
        if tool_input is None:
            raise ContractRunnerError(f"Tool input is unresolved for step {step_id}")
        input_data["tool_request"] = {
            "slug": tool_slug,
            "input": tool_input,
        }
    else:
        raise ContractRunnerError(f"Unsupported compiled step kind: {kind}")

    child = Task(
        organization_id=parent_task.organization_id,
        created_by_user_id=actor_user_id,
        assigned_agent_id=agent.id,
        title=f"{parent_task.title} · {step_id}",
        objective=str(
            step.get("objective")
            or f"Execute compiled contract step {step_id} for {parent_task.title}."
        ),
        priority=parent_task.priority,
        status=TaskStatus.ASSIGNED.value,
        input_data=input_data,
    )
    session.add(child)
    session.flush()
    session.add(
        TaskEvent(
            organization_id=parent_task.organization_id,
            task_id=child.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="compiled_contract.child_created",
            details={
                "parent_task_id": str(parent_task.id),
                "stage_id": _stage_id(parent_task),
                "step_id": step_id,
                "attempt": attempt,
                "repeat_index": repeat_index,
                "kind": kind,
            },
        )
    )
    session.commit()
    session.refresh(child)
    return child


def _safe_repository_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractRunnerError("Generated repository artifact path is empty")
    path = value.strip().replace("\\", "/")
    pure = PurePosixPath(path)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise ContractRunnerError("Generated repository artifact path is unsafe")
    normalized = pure.as_posix()
    lowered_parts = [part.casefold() for part in pure.parts]
    if ".git" in lowered_parts:
        raise ContractRunnerError("Generated repository artifact cannot write .git")
    lowered = normalized.casefold()
    if (
        lowered.startswith(".github/workflows/")
        or lowered.startswith(".circleci/")
        or lowered == ".circleci"
    ):
        raise ContractRunnerError(
            "Generated repository artifact cannot rewrite CI control files"
        )
    if len(normalized) > 300:
        raise ContractRunnerError("Generated repository artifact path is too long")
    return normalized


def _model_artifacts(task: Task) -> list[dict[str, str]]:
    output = task.output_data or {}
    structured = output.get("structured_output") if isinstance(output, dict) else None
    if not isinstance(structured, dict):
        raise ContractRunnerError("Model step has no validated structured output")
    raw = structured.get("artifacts")
    if not isinstance(raw, list) or not raw:
        raise ContractRunnerError("Model step returned no repository artifacts")
    if len(raw) > MAX_ARTIFACTS:
        raise ContractRunnerError("Model step returned too many repository artifacts")

    artifacts: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    total_chars = 0
    for item in raw:
        if not isinstance(item, dict):
            raise ContractRunnerError("Repository artifact must be an object")
        path = _safe_repository_path(item.get("path"))
        path_key = path.casefold()
        if path_key in seen_paths:
            raise ContractRunnerError("Repository artifact paths must be unique")
        seen_paths.add(path_key)
        content = item.get("content")
        message = item.get("message")
        if not isinstance(content, str):
            raise ContractRunnerError("Repository artifact content must be text")
        if len(content) > MAX_ARTIFACT_CONTENT_CHARS:
            raise ContractRunnerError("Repository artifact content exceeds limit")
        total_chars += len(content)
        if total_chars > MAX_TOTAL_ARTIFACT_CONTENT_CHARS:
            raise ContractRunnerError("Repository artifact batch exceeds content limit")
        if not isinstance(message, str) or not message.strip():
            raise ContractRunnerError("Repository artifact commit message is empty")
        artifacts.append(
            {
                "path": path,
                "content": content,
                "message": message.strip()[:240],
            }
        )
    return artifacts


def _value_at(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _tool_output(task: Task) -> dict[str, Any] | None:
    output = task.output_data or {}
    value = output.get("tool_output") if isinstance(output, dict) else None
    return value if isinstance(value, dict) else None


def _validated_tool_receipt(
    session: Session,
    *,
    child: Task,
    step: dict[str, Any],
) -> tuple[bool, str, dict[str, Any] | None]:
    output = child.output_data or {}
    if not isinstance(output, dict) or output.get("execution_type") != "tool":
        return False, "child_has_no_tool_execution", None
    if str(output.get("tool_slug") or "") != str(step.get("tool_slug") or ""):
        return False, "child_tool_slug_mismatch", None

    evidence = output.get("evidence")
    if not isinstance(evidence, dict):
        return False, "child_tool_evidence_missing", None
    try:
        run_id = UUID(str(evidence.get("tool_run_id") or ""))
    except ValueError:
        return False, "child_tool_run_reference_invalid", None

    run = session.get(ToolRun, run_id)
    if run is None:
        return False, "child_tool_run_not_found", None
    if run.organization_id != child.organization_id or run.task_id != child.id:
        return False, "child_tool_run_scope_mismatch", None
    if run.status != ToolRunStatus.SUCCEEDED.value:
        return False, "child_tool_run_not_succeeded", None

    expected_tool_id = step.get("tool_id")
    if expected_tool_id and str(run.tool_id) != str(expected_tool_id):
        return False, "child_tool_id_mismatch", None

    run_output = run.output_data or {}
    provider_evidence = (
        run_output.get("evidence")
        if isinstance(run_output, dict)
        else None
    )
    expected_receipt = (
        str(provider_evidence.get("receipt_id"))
        if isinstance(provider_evidence, dict)
        and provider_evidence.get("receipt_id")
        else f"tool-run:{run.id}"
    )
    receipt_id = str(evidence.get("receipt_id") or "")
    if receipt_id != expected_receipt:
        return False, "child_tool_receipt_mismatch", None

    return True, "verified_tool_receipt", {
        "step_id": str(step["id"]),
        "repeat_index": _child_repeat_index(child),
        "child_task_id": str(child.id),
        "tool_run_id": str(run.id),
        "receipt_id": receipt_id,
        "tool_output": run_output,
    }


def _acceptance_state(
    session: Session,
    *,
    child: Task,
    step: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None]:
    valid, reason, receipt = _validated_tool_receipt(
        session,
        child=child,
        step=step,
    )
    if not valid:
        return "failed", reason, None

    acceptance = step.get("acceptance")
    if not isinstance(acceptance, dict):
        return "passed", "receipt_verified", receipt
    tool_output = receipt["tool_output"] if receipt is not None else {}

    output_path = acceptance.get("output_path")
    if not isinstance(output_path, str) or not output_path:
        return "passed", "receipt_verified", receipt

    actual = _value_at(tool_output, output_path)
    expected_equal = acceptance.get("equals")
    expected_values = acceptance.get("in")
    if "equals" in acceptance and actual == expected_equal:
        return "passed", "acceptance_equals", receipt
    if (
        isinstance(expected_values, list)
        and actual in expected_values
    ):
        return "passed", "acceptance_in", receipt

    external_resource_path = acceptance.get("external_resource_path")
    external_resource_values = acceptance.get("external_resource_values")
    if (
        isinstance(external_resource_path, str)
        and isinstance(external_resource_values, list)
    ):
        resource_value = _value_at(tool_output, external_resource_path)
        if resource_value in external_resource_values:
            return (
                "external-resource",
                f"{external_resource_path}:{resource_value}",
                receipt,
            )

    pending_values = acceptance.get("pending_values")
    if isinstance(pending_values, list) and actual in pending_values:
        return "pending", f"acceptance_pending:{output_path}", receipt

    pending_status_path = acceptance.get("pending_status_path")
    pending_status_values = acceptance.get("pending_status_values")
    if (
        isinstance(pending_status_path, str)
        and isinstance(pending_status_values, list)
    ):
        status_value = _value_at(tool_output, pending_status_path)
        if status_value in pending_status_values:
            return (
                "pending",
                f"acceptance_pending:{pending_status_path}",
                receipt,
            )

    return (
        "failed",
        f"acceptance_failed:{output_path}:{actual!r}",
        receipt,
    )


def _retry_safe(step: dict[str, Any]) -> bool:
    key = (
        str(step.get("provider") or "").lower(),
        str(step.get("action_name") or ""),
    )
    return key in _RETRY_SAFE_READ_ACTIONS


def _step_outputs(
    session: Session,
    *,
    children: list[Task],
    contract: dict[str, Any],
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    steps = {
        str(step["id"]): step
        for step in contract.get("steps") or []
        if isinstance(step, dict) and step.get("id")
    }
    for child in children:
        if TaskStatus(child.status) is not TaskStatus.SUCCEEDED:
            continue
        step_id = _child_step_id(child)
        step = steps.get(str(step_id)) if step_id else None
        if step is None or step.get("kind") != "tool":
            continue
        state, _reason, receipt = _acceptance_state(
            session,
            child=child,
            step=step,
        )
        if state != "passed" or receipt is None:
            continue
        if _child_repeat_index(child) is None:
            outputs[str(step_id)] = receipt["tool_output"]
    return outputs


def _resolve_binding(
    source: str,
    *,
    artifact: dict[str, str] | None,
    outputs: dict[str, Any],
    parent_task: Task,
) -> tuple[bool, Any]:
    if source.startswith("model.artifacts[*]."):
        if artifact is None:
            return False, None
        field = source.removeprefix("model.artifacts[*].")
        value = artifact.get(field)
        return value is not None, value

    if source.startswith("steps."):
        remainder = source.removeprefix("steps.")
        step_id, separator, output_path = remainder.partition(".output.")
        if not separator or step_id not in outputs:
            return False, None
        value = _value_at(outputs[step_id], output_path)
        return value is not None, value

    if source == "upstream.verified_commit_sha":
        upstream = (parent_task.input_data or {}).get("upstream_evidence")
        if isinstance(upstream, dict):
            value = upstream.get("verified_commit_sha")
            return value is not None, value
        return False, None

    return False, None


def _tool_payload(
    step: dict[str, Any],
    *,
    artifact: dict[str, str] | None,
    outputs: dict[str, Any],
    parent_task: Task,
) -> tuple[dict[str, Any] | None, list[str]]:
    raw_input = step.get("input")
    payload = dict(raw_input) if isinstance(raw_input, dict) else {}
    bindings = step.get("bindings")
    unresolved: list[str] = []
    if isinstance(bindings, dict):
        for field, source in bindings.items():
            if not isinstance(source, str):
                unresolved.append(str(field))
                continue
            resolved, value = _resolve_binding(
                source,
                artifact=artifact,
                outputs=outputs,
                parent_task=parent_task,
            )
            if not resolved:
                unresolved.append(str(field))
                continue
            payload[str(field)] = value

    missing = step.get("missing_fields")
    if isinstance(missing, list):
        for field in missing:
            value = payload.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                unresolved.append(str(field))

    return (payload if not unresolved else None), sorted(set(unresolved))


def _chain_receipt_id(
    *,
    parent_task: Task,
    contract_version: str,
    model_task_id: str | None,
    receipts: list[dict[str, Any]],
) -> str:
    normalized = [
        {
            key: item.get(key)
            for key in (
                "step_id",
                "repeat_index",
                "child_task_id",
                "tool_run_id",
                "receipt_id",
            )
        }
        for item in receipts
    ]
    material = json.dumps(
        {
            "parent_task_id": str(parent_task.id),
            "contract_version": contract_version,
            "model_task_id": model_task_id,
            "receipts": normalized,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"contract-chain:{digest}"


def verify_compiled_contract_evidence(
    session: Session,
    *,
    task: Task,
) -> tuple[bool, str, list[str]]:
    try:
        contract = _contract(task)
    except ContractRunnerError as exc:
        return False, str(exc), []

    output = task.output_data or {}
    if not isinstance(output, dict) or output.get("execution_type") != "compiled-contract":
        return False, "compiled_contract_output_missing", []
    chain = output.get("contract_chain")
    if not isinstance(chain, dict):
        return False, "compiled_contract_chain_missing", []

    model_steps = [
        step
        for step in contract.get("steps") or []
        if isinstance(step, dict) and step.get("kind") == "model"
    ]
    if len(model_steps) > 1:
        return False, "compiled_contract_multiple_model_steps_unsupported", []

    model_task: Task | None = None
    artifacts: list[dict[str, str]] = []
    model_task_id_raw = chain.get("model_task_id")
    if model_steps:
        try:
            model_task_id = UUID(str(model_task_id_raw))
        except (TypeError, ValueError):
            return False, "compiled_contract_model_task_invalid", []
        model_task = session.get(Task, model_task_id)
        if model_task is None:
            return False, "compiled_contract_model_task_missing", []
        if (
            model_task.organization_id != task.organization_id
            or (model_task.input_data or {}).get("contract_parent_task_id")
            != str(task.id)
            or TaskStatus(model_task.status) is not TaskStatus.SUCCEEDED
        ):
            return False, "compiled_contract_model_task_scope_invalid", []
        try:
            artifacts = _model_artifacts(model_task)
        except ContractRunnerError as exc:
            return False, str(exc), []
    elif model_task_id_raw not in {None, ""}:
        return False, "compiled_contract_unexpected_model_task", []

    raw_receipts = chain.get("receipts")
    if not isinstance(raw_receipts, list):
        return False, "compiled_contract_receipts_missing", []
    receipt_rows = [item for item in raw_receipts if isinstance(item, dict)]

    expected_tool_steps = [
        step
        for step in contract.get("steps") or []
        if isinstance(step, dict) and step.get("kind") == "tool"
    ]
    verified_refs: list[str] = []
    canonical_receipts: list[dict[str, Any]] = []
    for step in expected_tool_steps:
        step_id = str(step["id"])
        acceptance = step.get("acceptance")
        repeat = (
            isinstance(acceptance, dict)
            and acceptance.get("repeat_for_each") == "model.artifacts"
        )
        expected_count = len(artifacts) if repeat else 1
        rows = [
            row for row in receipt_rows
            if str(row.get("step_id") or "") == step_id
        ]
        if len(rows) != expected_count:
            return False, f"compiled_contract_receipt_count:{step_id}", []

        if repeat:
            try:
                indices = sorted(
                    int(row.get("repeat_index"))
                    for row in rows
                    if row.get("repeat_index") is not None
                )
            except (TypeError, ValueError):
                return False, f"compiled_contract_repeat_index:{step_id}", []
            if indices != list(range(expected_count)):
                return False, f"compiled_contract_repeat_index:{step_id}", []

        for row in rows:
            try:
                child_id = UUID(str(row.get("child_task_id") or ""))
            except ValueError:
                return False, f"compiled_contract_child_invalid:{step_id}", []
            child = session.get(Task, child_id)
            if child is None:
                return False, f"compiled_contract_child_missing:{step_id}", []
            if (
                child.organization_id != task.organization_id
                or (child.input_data or {}).get("contract_parent_task_id")
                != str(task.id)
                or _child_step_id(child) != step_id
                or TaskStatus(child.status) is not TaskStatus.SUCCEEDED
            ):
                return False, f"compiled_contract_child_scope:{step_id}", []

            state, reason, receipt = _acceptance_state(
                session,
                child=child,
                step=step,
            )
            if state != "passed" or receipt is None:
                return False, f"compiled_contract_acceptance:{step_id}:{reason}", []
            for key in ("tool_run_id", "receipt_id"):
                if str(row.get(key) or "") != str(receipt.get(key) or ""):
                    return False, f"compiled_contract_receipt_mismatch:{step_id}", []
            canonical_receipts.append(receipt)
            verified_refs.extend(
                [
                    f"receipt:{receipt['receipt_id']}",
                    f"tool-run:{receipt['tool_run_id']}",
                ]
            )

    contract_version = str(contract.get("version") or "")
    expected_chain_receipt = _chain_receipt_id(
        parent_task=task,
        contract_version=contract_version,
        model_task_id=str(model_task.id) if model_task is not None else None,
        receipts=canonical_receipts,
    )
    evidence = output.get("evidence")
    if not (
        isinstance(evidence, dict)
        and str(evidence.get("receipt_id") or "") == expected_chain_receipt
    ):
        return False, "compiled_contract_chain_receipt_mismatch", []

    return True, "verified_compiled_contract", [
        f"receipt:{expected_chain_receipt}",
        *verified_refs,
    ]


def _blocked_report(
    *,
    task: Task,
    contract: dict[str, Any],
    reason: str,
    match_score: int | None = None,
    step_results: list[dict[str, Any]] | None = None,
    executed_steps: int = 0,
) -> dict[str, Any]:
    return {
        "runner_version": RUNNER_VERSION,
        "task_id": str(task.id),
        "stage_id": _stage_id(task),
        "contract_version": contract.get("version"),
        "status": "blocked",
        "reason": reason,
        "task_status": task.status,
        "assigned_agent_id": (
            str(task.assigned_agent_id) if task.assigned_agent_id else None
        ),
        "match_score": match_score,
        "executed_steps": executed_steps,
        "step_results": step_results or [],
        "verified": False,
        "evidence_refs": [],
    }


def advance_compiled_contract(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID,
    max_steps: int = 12,
    gateway: ModelGateway | None = None,
) -> dict[str, Any]:
    if not 1 <= max_steps <= 50:
        raise ContractRunnerError("max_steps must be between 1 and 50")
    contract = _contract(task)

    if str(contract.get("execution_mode") or "automatic") != "automatic":
        return _blocked_report(
            task=task,
            contract=contract,
            reason=f"execution_mode:{contract.get('execution_mode')}",
        )

    if TaskStatus(task.status) is TaskStatus.SUCCEEDED:
        verified, reason, refs = verify_compiled_contract_evidence(
            session,
            task=task,
        )
        return {
            **_blocked_report(
                task=task,
                contract=contract,
                reason=reason,
            ),
            "status": "verified" if verified else "unverified",
            "verified": verified,
            "evidence_refs": refs,
        }
    if TaskStatus(task.status) in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
        return _blocked_report(
            task=task,
            contract=contract,
            reason=f"parent_task_{task.status}",
        )

    tool_steps = [
        step
        for step in contract.get("steps") or []
        if isinstance(step, dict) and step.get("kind") == "tool"
    ]
    if not tool_steps:
        return _blocked_report(
            task=task,
            contract=contract,
            reason="contract_has_no_machine_evidence_steps",
        )

    unavailable = [
        str(step.get("id"))
        for step in tool_steps
        if not step.get("tool_slug")
    ]
    if unavailable:
        return _blocked_report(
            task=task,
            contract=contract,
            reason="compiled_tools_unavailable:" + ",".join(unavailable),
        )

    unresolved_inputs = [
        (
            str(step.get("id")),
            [
                str(field)
                for field in step.get("missing_fields") or []
            ],
        )
        for step in tool_steps
        if step.get("status") == "input-unresolved"
    ]
    if unresolved_inputs:
        details = ";".join(
            f"{step_id}:{','.join(fields)}"
            for step_id, fields in unresolved_inputs
        )
        return _blocked_report(
            task=task,
            contract=contract,
            reason=f"compiled_inputs_unresolved:{details}",
        )

    agent, match_score = _assign_parent_agent(
        session,
        task=task,
        actor_user_id=actor_user_id,
    )
    if agent is None:
        return _blocked_report(
            task=task,
            contract=contract,
            reason="no_capable_active_agent",
            match_score=match_score,
        )

    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="compiled_contract.advance.started",
        resource_type="task",
        resource_id=str(task.id),
        details={
            "runner_version": RUNNER_VERSION,
            "stage_id": _stage_id(task),
            "contract_version": contract.get("version"),
            "max_steps": max_steps,
        },
    )
    session.commit()

    executed_steps = 0
    step_results: list[dict[str, Any]] = []
    accepted_receipts: list[dict[str, Any]] = []
    model_task: Task | None = None
    artifacts: list[dict[str, str]] = []

    for step in contract.get("steps") or []:
        if not isinstance(step, dict):
            return _blocked_report(
                task=task,
                contract=contract,
                reason="compiled_step_invalid",
                match_score=match_score,
                step_results=step_results,
                executed_steps=executed_steps,
            )
        step_id = str(step.get("id") or "")
        kind = str(step.get("kind") or "")
        children = _child_tasks(session, parent_task=task)

        if kind == "model":
            child = _latest_child(children, step_id=step_id)
            if child is None:
                if executed_steps >= max_steps:
                    return _blocked_report(
                        task=task,
                        contract=contract,
                        reason="step_limit",
                        match_score=match_score,
                        step_results=step_results,
                        executed_steps=executed_steps,
                    )
                child = _new_child_task(
                    session,
                    parent_task=task,
                    agent=agent,
                    actor_user_id=actor_user_id,
                    step=step,
                )

            status = TaskStatus(child.status)
            if status is TaskStatus.ASSIGNED:
                if executed_steps >= max_steps:
                    return _blocked_report(
                        task=task,
                        contract=contract,
                        reason="step_limit",
                        match_score=match_score,
                        step_results=step_results,
                        executed_steps=executed_steps,
                    )
                try:
                    execute_agent_task(
                        session,
                        task=child,
                        agent=agent,
                        actor_user_id=actor_user_id,
                        gateway=gateway,
                    )
                except AgentRuntimeError as exc:
                    step_results.append(
                        {
                            "step_id": step_id,
                            "kind": kind,
                            "status": "failed",
                            "reason": str(exc),
                            "child_task_id": str(child.id),
                        }
                    )
                    return _blocked_report(
                        task=task,
                        contract=contract,
                        reason=f"model_step_failed:{step_id}",
                        match_score=match_score,
                        step_results=step_results,
                        executed_steps=executed_steps + 1,
                    )
                executed_steps += 1
                session.refresh(child)
                status = TaskStatus(child.status)

            if status is not TaskStatus.SUCCEEDED:
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=f"model_step_{status.value}:{step_id}",
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )
            try:
                artifacts = _model_artifacts(child)
            except ContractRunnerError as exc:
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=str(exc),
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )
            model_task = child
            step_results.append(
                {
                    "step_id": step_id,
                    "kind": kind,
                    "status": "accepted",
                    "child_task_id": str(child.id),
                    "artifact_count": len(artifacts),
                }
            )
            continue

        if kind != "tool":
            return _blocked_report(
                task=task,
                contract=contract,
                reason=f"unsupported_step_kind:{kind}",
                match_score=match_score,
                step_results=step_results,
                executed_steps=executed_steps,
            )

        outputs = _step_outputs(
            session,
            children=children,
            contract=contract,
        )
        acceptance = step.get("acceptance")
        repeat = (
            isinstance(acceptance, dict)
            and acceptance.get("repeat_for_each") == "model.artifacts"
        )
        repetitions = list(enumerate(artifacts)) if repeat else [(None, None)]
        if repeat and not artifacts:
            return _blocked_report(
                task=task,
                contract=contract,
                reason=f"repeat_source_missing:{step_id}",
                match_score=match_score,
                step_results=step_results,
                executed_steps=executed_steps,
            )

        for repeat_index, artifact in repetitions:
            children = _child_tasks(session, parent_task=task)
            child = _latest_child(
                children,
                step_id=step_id,
                repeat_index=repeat_index,
            )
            if child is not None and TaskStatus(child.status) is TaskStatus.SUCCEEDED:
                state, reason, receipt = _acceptance_state(
                    session,
                    child=child,
                    step=step,
                )
                if state == "passed" and receipt is not None:
                    accepted_receipts.append(receipt)
                    step_results.append(
                        {
                            "step_id": step_id,
                            "kind": kind,
                            "repeat_index": repeat_index,
                            "status": "accepted",
                            "reason": reason,
                            "child_task_id": str(child.id),
                            "receipt_id": receipt["receipt_id"],
                        }
                    )
                    continue
                if state == "external-resource":
                    step_results.append(
                        {
                            "step_id": step_id,
                            "kind": kind,
                            "repeat_index": repeat_index,
                            "status": "external-resource",
                            "reason": reason,
                            "child_task_id": str(child.id),
                        }
                    )
                    return _blocked_report(
                        task=task,
                        contract=contract,
                        reason=f"external_resource:{step_id}:{reason}",
                        match_score=match_score,
                        step_results=step_results,
                        executed_steps=executed_steps,
                    )
                if state == "failed":
                    step_results.append(
                        {
                            "step_id": step_id,
                            "kind": kind,
                            "repeat_index": repeat_index,
                            "status": "failed",
                            "reason": reason,
                            "child_task_id": str(child.id),
                        }
                    )
                    return _blocked_report(
                        task=task,
                        contract=contract,
                        reason=f"acceptance_failed:{step_id}",
                        match_score=match_score,
                        step_results=step_results,
                        executed_steps=executed_steps,
                    )
                if not _retry_safe(step):
                    return _blocked_report(
                        task=task,
                        contract=contract,
                        reason=f"acceptance_pending:{step_id}",
                        match_score=match_score,
                        step_results=step_results,
                        executed_steps=executed_steps,
                    )
                child = None

            if child is not None and TaskStatus(child.status) in {
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=f"tool_child_{child.status}:{step_id}",
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )

            payload, unresolved = _tool_payload(
                step,
                artifact=artifact,
                outputs=outputs,
                parent_task=task,
            )
            if payload is None:
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=(
                        f"binding_unresolved:{step_id}:"
                        + ",".join(unresolved)
                    ),
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )

            if child is None:
                if executed_steps >= max_steps:
                    return _blocked_report(
                        task=task,
                        contract=contract,
                        reason="step_limit",
                        match_score=match_score,
                        step_results=step_results,
                        executed_steps=executed_steps,
                    )
                child = _new_child_task(
                    session,
                    parent_task=task,
                    agent=agent,
                    actor_user_id=actor_user_id,
                    step=step,
                    repeat_index=repeat_index,
                    tool_input=payload,
                )

            if TaskStatus(child.status) is not TaskStatus.ASSIGNED:
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=f"tool_child_{child.status}:{step_id}",
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )

            tool_status, tool_reason = _execute_registered_tool(
                session,
                task=child,
                agent=agent,
                actor_user_id=actor_user_id,
                confirmed_sensitive_action=False,
            )
            if tool_status == "approval_required":
                step_results.append(
                    {
                        "step_id": step_id,
                        "kind": kind,
                        "repeat_index": repeat_index,
                        "status": "approval_required",
                        "reason": tool_reason,
                        "child_task_id": str(child.id),
                    }
                )
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=f"approval_required:{step_id}",
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )
            if tool_status != "succeeded":
                step_results.append(
                    {
                        "step_id": step_id,
                        "kind": kind,
                        "repeat_index": repeat_index,
                        "status": tool_status,
                        "reason": tool_reason,
                        "child_task_id": str(child.id),
                    }
                )
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=f"tool_step_{tool_status}:{step_id}",
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )

            executed_steps += 1
            session.refresh(child)
            state, reason, receipt = _acceptance_state(
                session,
                child=child,
                step=step,
            )
            if state == "passed" and receipt is not None:
                accepted_receipts.append(receipt)
                step_results.append(
                    {
                        "step_id": step_id,
                        "kind": kind,
                        "repeat_index": repeat_index,
                        "status": "accepted",
                        "reason": reason,
                        "child_task_id": str(child.id),
                        "receipt_id": receipt["receipt_id"],
                    }
                )
                continue
            if state == "external-resource":
                step_results.append(
                    {
                        "step_id": step_id,
                        "kind": kind,
                        "repeat_index": repeat_index,
                        "status": "external-resource",
                        "reason": reason,
                        "child_task_id": str(child.id),
                    }
                )
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=f"external_resource:{step_id}:{reason}",
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )
            if state == "pending":
                step_results.append(
                    {
                        "step_id": step_id,
                        "kind": kind,
                        "repeat_index": repeat_index,
                        "status": "pending",
                        "reason": reason,
                        "child_task_id": str(child.id),
                    }
                )
                return _blocked_report(
                    task=task,
                    contract=contract,
                    reason=f"acceptance_pending:{step_id}",
                    match_score=match_score,
                    step_results=step_results,
                    executed_steps=executed_steps,
                )
            return _blocked_report(
                task=task,
                contract=contract,
                reason=f"acceptance_failed:{step_id}:{reason}",
                match_score=match_score,
                step_results=step_results,
                executed_steps=executed_steps,
            )

    chain_receipt = _chain_receipt_id(
        parent_task=task,
        contract_version=str(contract.get("version") or ""),
        model_task_id=str(model_task.id) if model_task is not None else None,
        receipts=accepted_receipts,
    )
    output = {
        "text": (
            "Compiled execution contract completed with machine-verifiable "
            "tool receipts."
        ),
        "execution_type": "compiled-contract",
        "contract_version": contract.get("version"),
        "contract_runner_version": RUNNER_VERSION,
        "stage_id": _stage_id(task),
        "contract_chain": {
            "model_task_id": (
                str(model_task.id) if model_task is not None else None
            ),
            "model_artifact_count": len(artifacts),
            "receipts": accepted_receipts,
            "completed_step_ids": [
                str(step.get("id"))
                for step in contract.get("steps") or []
                if isinstance(step, dict)
            ],
        },
        "evidence": {
            "receipt_id": chain_receipt,
        },
    }
    task.output_data = output
    verified, reason, refs = verify_compiled_contract_evidence(
        session,
        task=task,
    )
    if not verified:
        task.output_data = None
        return _blocked_report(
            task=task,
            contract=contract,
            reason=reason,
            match_score=match_score,
            step_results=step_results,
            executed_steps=executed_steps,
        )

    output["cognitive_verification"] = {
        "status": "verified",
        "reason": reason,
        "evidence_refs": refs,
        "runner_version": RUNNER_VERSION,
    }
    if TaskStatus(task.status) is TaskStatus.ASSIGNED:
        transition_task(task, TaskStatus.RUNNING)
    if TaskStatus(task.status) is not TaskStatus.RUNNING:
        raise ContractRunnerError(
            f"Parent task cannot complete from status {task.status}"
        )
    transition_task(
        task,
        TaskStatus.SUCCEEDED,
        output_data=output,
    )
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="compiled_contract.completed",
            details={
                "stage_id": _stage_id(task),
                "contract_version": contract.get("version"),
                "runner_version": RUNNER_VERSION,
                "receipt_id": chain_receipt,
                "tool_receipt_count": len(accepted_receipts),
            },
        )
    )
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            actor_agent_id=agent.id,
            event_type="cognitive_mission.stage_verified",
            details={
                "stage_id": _stage_id(task),
                "reason": reason,
                "evidence_refs": refs,
            },
        )
    )
    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="compiled_contract.completed",
        resource_type="task",
        resource_id=str(task.id),
        details={
            "stage_id": _stage_id(task),
            "contract_version": contract.get("version"),
            "runner_version": RUNNER_VERSION,
            "receipt_id": chain_receipt,
            "tool_receipt_count": len(accepted_receipts),
        },
    )
    session.commit()
    session.refresh(task)

    return {
        "runner_version": RUNNER_VERSION,
        "task_id": str(task.id),
        "stage_id": _stage_id(task),
        "contract_version": contract.get("version"),
        "status": "verified",
        "reason": reason,
        "task_status": task.status,
        "assigned_agent_id": str(agent.id),
        "match_score": match_score,
        "executed_steps": executed_steps,
        "step_results": step_results,
        "verified": True,
        "evidence_refs": refs,
    }
