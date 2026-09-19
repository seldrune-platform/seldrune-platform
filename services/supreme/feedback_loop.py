"""Feedback routing from failed verification into Seldrune learning."""

from dataclasses import dataclass

from .learning_loop import LearningObjective, create_learning_objective
from .verifiers import CheckResult, CheckState


@dataclass(frozen=True)
class VerificationGap:
    check_name: str
    measured: float | None
    threshold: float | None
    evidence: str


def failed_gaps(checks: tuple[CheckResult, ...]) -> tuple[VerificationGap, ...]:
    return tuple(
        VerificationGap(
            check.name,
            check.measured,
            check.threshold,
            check.evidence,
        )
        for check in checks
        if check.state is CheckState.FAIL
    )


def learning_objectives(
    skill_id: str,
    checks: tuple[CheckResult, ...],
) -> tuple[LearningObjective, ...]:
    gaps = failed_gaps(checks)
    return tuple(
        create_learning_objective(
            skill_id,
            f"{gap.check_name}: measured={gap.measured}, threshold={gap.threshold}",
        )
        for gap in gaps
    )
