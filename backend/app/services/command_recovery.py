from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.orchestration import OrchestrationRun
from backend.app.services.adaptive_planning import build_adaptive_planning_guidance
from backend.app.services.audit import record_audit
from backend.app.services.founding_agents import ensure_founding_agents
from backend.app.services.live_planner import build_live_plan
from backend.app.services.orchestrator import create_orchestration_run
from backend.app.services.outcome_verification import assess_command_outcome
from backend.app.services.playbook_engine import consolidate_playbooks
from backend.app.services.playbook_guidance import build_playbook_guidance
from backend.app.services.playbook_overlay import merge_playbook


class CommandRecoveryError(RuntimeError):
    pass


def create_recovery_command(
    session: Session,
    *,
    source_run: OrchestrationRun,
    actor_user_id: UUID,
) -> OrchestrationRun:
    assessment = assess_command_outcome(session, run=source_run)
    if source_run.status != "succeeded":
        raise CommandRecoveryError("Complete the original command before creating recovery")
    if assessment.promotable:
        raise CommandRecoveryError("This outcome is already verified and does not need recovery")

    existing_id = ((source_run.context or {}).get("owner_command") or {}).get(
        "recovery_command_id"
    )
    if existing_id:
        existing = session.get(OrchestrationRun, UUID(existing_id))
        if existing is not None and existing.organization_id == source_run.organization_id:
            return existing

    reasons = "; ".join(assessment.reasons) or "Outcome evidence requires review"
    objective = (
        f'Recover and verify the outcome for: "{source_run.objective}". '
        f"Resolve these blockers: {reasons} "
        "Repeat the required validation with direct evidence, clearly state whether the "
        "objective was achieved, and do not claim success unless the evidence supports it."
    )[:4000]

    ensure_founding_agents(
        session,
        organization_id=source_run.organization_id,
        created_by_user_id=actor_user_id,
    )
    consolidate_playbooks(
        session,
        organization_id=source_run.organization_id,
        actor_user_id=actor_user_id,
    )
    playbook_guidance = build_playbook_guidance(
        session,
        organization_id=source_run.organization_id,
        objective=objective,
    )
    adaptive_guidance = build_adaptive_planning_guidance(
        session,
        organization_id=source_run.organization_id,
        objective=objective,
    )
    guidance = merge_playbook(adaptive_guidance, playbook_guidance)
    planned = build_live_plan(objective, adaptive_guidance=guidance)
    context = {
        "owner_command": {
            "approval_status": "awaiting_approval",
            "approved_by": None,
            "recovery_of": str(source_run.id),
        },
        "planner": planned.metadata,
        "operational_playbook": playbook_guidance,
        "recovery": {
            "source_command_id": str(source_run.id),
            "source_outcome": assessment.to_dict(),
        },
    }
    recovery = create_orchestration_run(
        session,
        organization_id=source_run.organization_id,
        created_by_user_id=actor_user_id,
        objective=objective,
        context=context,
        plan=planned.steps,
    )
    recovery.planner_version = planned.planner_version

    owner_command = (source_run.context or {}).get("owner_command") or {}
    source_run.context = {
        **(source_run.context or {}),
        "owner_command": {
            **owner_command,
            "recovery_command_id": str(recovery.id),
        },
    }
    details = {
        "source_command_id": str(source_run.id),
        "recovery_command_id": str(recovery.id),
        "source_outcome": assessment.to_dict(),
        "step_count": len(planned.steps),
    }
    record_audit(
        session,
        organization_id=source_run.organization_id,
        actor_user_id=actor_user_id,
        action="owner_command.recovery_created",
        resource_type="orchestration",
        resource_id=str(recovery.id),
        details=details,
    )
    return recovery
