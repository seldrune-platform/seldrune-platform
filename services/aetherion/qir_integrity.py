"""Structural integrity validation for Aetherion Q-IR."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram


@dataclass(frozen=True)
class IntegrityReceipt:
    valid: bool
    operation_count: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def validate_integrity(program: QIRProgram) -> IntegrityReceipt:
    seen: set[str] = set()
    for op in program.operations:
        if op.op_id in seen:
            return IntegrityReceipt(False, len(program.operations))
        if any(item not in seen for item in op.inputs):
            return IntegrityReceipt(False, len(program.operations))
        seen.add(op.op_id)
    return IntegrityReceipt(program.output_id in seen, len(program.operations))
