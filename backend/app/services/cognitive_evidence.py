from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.tools import ToolRunStatus
from backend.app.models.task import Task
from backend.app.models.tool_run import ToolRun
from backend.app.services.contract_runner import verify_compiled_contract_evidence


def verify_task_completion_evidence(
    session: Session,
    *,
    task: Task,
) -> tuple[bool, str, list[str]]:
    output = task.output_data or {}
    if not isinstance(output, dict):
        return False, "missing_structured_output", []

    if output.get("execution_type") == "compiled-contract":
        return verify_compiled_contract_evidence(
            session,
            task=task,
        )

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
