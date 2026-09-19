"""Composite Q-IR reduction and correctness verifier."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram, execute
from .qir_equivalence import reduce_common_subexpressions
from .qir_pruning import prune_dead_states


@dataclass(frozen=True)
class VerificationReceipt:
    baseline_output: int
    optimized_output: int
    baseline_operations: int
    optimized_operations: int
    operations_eliminated: int
    equivalent: bool
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_benchmark: bool = False


def optimize_and_verify(program: QIRProgram) -> VerificationReceipt:
    baseline_output, baseline_ops = execute(program)
    optimized = prune_dead_states(reduce_common_subexpressions(program))
    optimized_output, optimized_ops = execute(optimized)
    return VerificationReceipt(
        baseline_output,
        optimized_output,
        baseline_ops,
        optimized_ops,
        baseline_ops - optimized_ops,
        baseline_output == optimized_output,
    )
