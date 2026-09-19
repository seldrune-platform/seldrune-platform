"""Reversible execution accounting for Aetherion Q-IR research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIROpcode, QIRProgram, execute


@dataclass(frozen=True)
class ReversibleReceipt:
    output: int
    operation_count: int
    logically_reversible_operations: int
    irreversible_operations: int
    reversible_fraction: float
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False


def analyze_reversibility(program: QIRProgram) -> ReversibleReceipt:
    output, count = execute(program)
    reversible = sum(op.opcode is QIROpcode.XOR for op in program.operations)
    irreversible = count - reversible
    return ReversibleReceipt(
        output,
        count,
        reversible,
        irreversible,
        reversible / count if count else 0.0,
    )
