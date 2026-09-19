"""Verifier adapters turn measured outcomes into Proof Mesh checks."""

from dataclasses import dataclass
from enum import StrEnum


class CheckState(StrEnum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    name: str
    state: CheckState
    evidence: str
    measured: float | None = None
    threshold: float | None = None


def threshold_check(
    name: str,
    measured: float,
    threshold: float,
    evidence: str,
    *,
    lower_is_better: bool = False,
) -> CheckResult:
    if not evidence.strip():
        raise ValueError("verification evidence is required")
    passed = measured <= threshold if lower_is_better else measured >= threshold
    return CheckResult(
        name,
        CheckState.PASS if passed else CheckState.FAIL,
        evidence,
        measured,
        threshold,
    )


def all_checks_pass(checks: tuple[CheckResult, ...]) -> bool:
    if not checks:
        raise ValueError("at least one verifier result is required")
    return all(check.state is CheckState.PASS for check in checks)
