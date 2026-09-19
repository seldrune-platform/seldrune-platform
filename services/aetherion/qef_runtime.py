"""Executable Quantum Execution Field simulator layer."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_pipeline_v2 import run_pipeline_v2


@dataclass(frozen=True)
class QEFReceipt:
    input_states: int
    surviving_states: int
    eliminated_states: int
    equivalent: bool
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False


def execute_field(program: QIRProgram) -> QEFReceipt:
    result = run_pipeline_v2(program)
    surviving = result.optimized_operations
    return QEFReceipt(
        result.baseline_operations,
        surviving,
        result.baseline_operations - surviving,
        result.equivalent,
    )
