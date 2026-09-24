from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.task import Task
from backend.app.services.contract_runner import (
    ContractRunnerError,
    advance_compiled_contract,
)
from backend.app.services.model_gateway import ModelGateway


RECOVERY_VERSION = "contract-recovery-v1"


_RETRYABLE_PREFIXES = (
    "acceptance_pending:",
    "tool_step_blocked:",
    "tool_child_running:",
    "model_step_running:",
)
_APPROVAL_PREFIXES = (
    "approval_required:",
    "execution_mode:owner-gated",
)
_CONFIGURATION_PREFIXES = (
    "compiled_tools_unavailable:",
    "compiled_inputs_unresolved:",
    "binding_unresolved:",
    "no_capable_active_agent",
    "repeat_source_missing:",
)
_RESOURCE_PREFIXES = (
    "execution_mode:external-resource",
)
_FAILURE_PREFIXES = (
    "model_step_failed:",
    "tool_step_failed:",
    "acceptance_failed:",
    "tool_child_failed:",
    "parent_task_failed",
    "parent_task_cancelled",
)


def classify_contract_blocker(
    *,
    status: str,
    reason: str | None,
) -> str:
    normalized_status = status.strip().lower()
    normalized_reason = (reason or "").strip()

    if normalized_status == "verified":
        return "complete"
    if normalized_status == "unverified":
        return "unverified"
    if normalized_reason == "step_limit":
        return "retryable"
    if normalized_reason.startswith(_RETRYABLE_PREFIXES):
        return "retryable"
    if normalized_reason.startswith(_APPROVAL_PREFIXES):
        return "approval"
    if normalized_reason.startswith(_RESOURCE_PREFIXES):
        return "external-resource"
    if normalized_reason.startswith(_CONFIGURATION_PREFIXES):
        return "configuration"
    if normalized_reason.startswith(_FAILURE_PREFIXES):
        return "failed"
    if normalized_status == "failed":
        return "failed"
    return "blocked"


def advance_contract_with_recovery(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID,
    max_steps: int = 12,
    max_rounds: int = 3,
    gateway: ModelGateway | None = None,
) -> dict[str, Any]:
    if not 1 <= max_rounds <= 5:
        raise ContractRunnerError("max_rounds must be between 1 and 5")

    attempts: list[dict[str, Any]] = []
    final_report: dict[str, Any] | None = None

    for round_number in range(1, max_rounds + 1):
        report = advance_compiled_contract(
            session,
            task=task,
            actor_user_id=actor_user_id,
            max_steps=max_steps,
            gateway=gateway,
        )
        final_report = report
        status = str(report.get("status") or "blocked")
        reason = (
            str(report.get("reason"))
            if report.get("reason") is not None
            else None
        )
        classification = classify_contract_blocker(
            status=status,
            reason=reason,
        )
        attempts.append(
            {
                "round": round_number,
                "status": status,
                "reason": reason,
                "classification": classification,
                "executed_steps": int(report.get("executed_steps") or 0),
                "verified": bool(report.get("verified")),
            }
        )

        if classification != "retryable":
            break

    if final_report is None:
        raise ContractRunnerError("Contract recovery produced no execution report")

    final_status = str(final_report.get("status") or "blocked")
    final_reason = (
        str(final_report.get("reason"))
        if final_report.get("reason") is not None
        else None
    )
    final_classification = classify_contract_blocker(
        status=final_status,
        reason=final_reason,
    )
    recovery = {
        "version": RECOVERY_VERSION,
        "rounds_requested": max_rounds,
        "rounds_executed": len(attempts),
        "attempts": attempts,
        "final_classification": final_classification,
        "retryable_remaining": final_classification == "retryable",
        "requires_owner_action": final_classification == "approval",
        "requires_external_resource": final_classification == "external-resource",
        "requires_configuration": final_classification == "configuration",
    }
    return {
        **final_report,
        "recovery": recovery,
    }
