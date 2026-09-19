"""Proof Mesh evidence gate for executable STI work."""

from dataclasses import dataclass
from enum import StrEnum

from .worker_runtime import WorkResult, validate_result


class ProofVerdict(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Proof:
    task_id: str
    verdict: ProofVerdict
    checks: tuple[str, ...]
    evidence: tuple[str, ...]


def evaluate_result(
    result: WorkResult,
    required_checks: tuple[str, ...] = ("execution",),
) -> Proof:
    validate_result(result)
    if not required_checks:
        raise ValueError("at least one proof check is required")
    if not result.succeeded:
        return Proof(
            result.task_id,
            ProofVerdict.REJECTED,
            required_checks,
            result.evidence,
        )
    return Proof(
        result.task_id,
        ProofVerdict.VERIFIED,
        required_checks,
        result.evidence,
    )
