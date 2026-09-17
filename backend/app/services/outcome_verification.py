from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.orchestration import OrchestrationRun, OrchestrationStep
from backend.app.models.task import Task


OUTCOME_GATE_VERSION = "outcome-gate-v2"
_BLOCKER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bnot ready\b", "The result explicitly declares that it is not ready."),
    (r"\b(?:has|have|was|were)?\s*not been verified\b", "Required verification is incomplete."),
    (r"\bnot verified\b", "Required verification is incomplete."),
    (r"\brequired verification is incomplete\b", "Required verification is incomplete."),
    (r"\bdo not mark\b", "The result explicitly rejects a successful conclusion."),
    (r"\bcannot confirm\b", "The result cannot confirm the objective."),
    (r"\bunable to verify\b", "The result could not verify the objective."),
    (r"\bvalidation (?:has )?failed\b", "Validation failed."),
    (r"\bfailed validation\b", "Validation failed."),
    (r"\bobjective (?:was |is )?not achieved\b", "The objective was not achieved."),
)
_REVIEW_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\brequires? (?:owner |human )?review\b", "The result requires owner review."),
    (r"\binsufficient evidence\b", "The result reports insufficient evidence."),
    (r"\bneeds? (?:owner |human )?approval\b", "The result needs an explicit review."),
)
_DIAGNOSTIC_OBJECTIVE_PATTERNS = (
    r"\banaly[sz]e\b",
    r"\bassess(?:ment)?\b",
    r"\breview\b",
    r"\bidentify (?:gaps|risks|issues|priorities)\b",
    r"\breadiness assessment\b",
    r"\bproduce (?:a |an )?(?:report|brief|plan|assessment)\b",
)
_VERIFICATION_OBJECTIVE_PATTERNS = (
    r"\bverify\b",
    r"\bvalidate\b",
    r"\bconfirm\b",
    r"\bprove\b",
    r"\btest whether\b",
    r"\bensure .{0,80}\b(?:ready|working|passed|complete)\b",
)


@dataclass(frozen=True)
class OutcomeAssessment:
    verdict: str
    promotable: bool
    reasons: list[str]
    evidence_step: int | None
    version: str = OUTCOME_GATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _first_match(text: str, patterns: tuple[tuple[str, str], ...]) -> str | None:
    normalized = " ".join(text.lower().split())
    for pattern, reason in patterns:
        if re.search(pattern, normalized):
            return reason
    return None


def _objective_is_diagnostic(objective: str) -> bool:
    normalized = " ".join((objective or "").lower().split())
    diagnostic = any(
        re.search(pattern, normalized) for pattern in _DIAGNOSTIC_OBJECTIVE_PATTERNS
    )
    verification = any(
        re.search(pattern, normalized) for pattern in _VERIFICATION_OBJECTIVE_PATTERNS
    )
    return diagnostic and not verification


def assess_command_outcome(
    session: Session,
    *,
    run: OrchestrationRun,
) -> OutcomeAssessment:
    steps = list(
        session.scalars(
            select(OrchestrationStep)
            .where(OrchestrationStep.orchestration_run_id == run.id)
            .order_by(OrchestrationStep.sequence)
        )
    )
    tasks_by_id: dict[UUID, Task] = {
        step.task_id: task
        for step in steps
        if (task := session.get(Task, step.task_id)) is not None
    }
    if run.status != "succeeded" or not steps:
        return OutcomeAssessment(
            verdict="not_achieved",
            promotable=False,
            reasons=["Execution has not completed successfully."],
            evidence_step=None,
        )

    diagnostic_objective = _objective_is_diagnostic(run.objective)
    for step in reversed(steps):
        task = tasks_by_id.get(step.task_id)
        text = (task.output_data or {}).get("text") if task else None
        if not isinstance(text, str) or not text.strip():
            continue
        blocker = _first_match(text, _BLOCKER_PATTERNS)
        if blocker and not diagnostic_objective:
            return OutcomeAssessment(
                verdict="not_achieved",
                promotable=False,
                reasons=[blocker],
                evidence_step=step.sequence,
            )

    final_step = steps[-1]
    final_task = tasks_by_id.get(final_step.task_id)
    final_text = (final_task.output_data or {}).get("text") if final_task else None
    if not isinstance(final_text, str) or not final_text.strip():
        return OutcomeAssessment(
            verdict="review",
            promotable=False,
            reasons=["The final step has no evidence output to verify."],
            evidence_step=final_step.sequence,
        )
    review = _first_match(final_text, _REVIEW_PATTERNS)
    if review:
        return OutcomeAssessment(
            verdict="review",
            promotable=False,
            reasons=[review],
            evidence_step=final_step.sequence,
        )
    return OutcomeAssessment(
        verdict="achieved",
        promotable=True,
        reasons=["Execution completed and no objective-level outcome blocker was detected."],
        evidence_step=final_step.sequence,
    )
