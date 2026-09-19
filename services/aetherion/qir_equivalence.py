"""Baseline-vs-reduced Q-IR equivalence experiment."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIROp, QIROpcode, QIRProgram, execute


@dataclass(frozen=True)
class EquivalenceReceipt:
    baseline_output: int
    reduced_output: int
    baseline_operations: int
    reduced_operations: int
    equivalent: bool
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False


def reduce_common_subexpressions(program: QIRProgram) -> QIRProgram:
    aliases: dict[str, str] = {}
    signatures: dict[tuple[object, ...], str] = {}
    reduced: list[QIROp] = []

    for op in program.operations:
        inputs = tuple(aliases.get(item, item) for item in op.inputs)
        signature = (op.opcode, inputs, op.value)
        existing = signatures.get(signature)
        if existing is not None:
            aliases[op.op_id] = existing
            continue
        normalized = QIROp(op.op_id, op.opcode, inputs, op.value)
        signatures[signature] = op.op_id
        reduced.append(normalized)

    output_id = aliases.get(program.output_id, program.output_id)
    return QIRProgram(tuple(reduced), output_id)


def verify_equivalence(program: QIRProgram) -> EquivalenceReceipt:
    baseline_output, baseline_ops = execute(program)
    reduced = reduce_common_subexpressions(program)
    reduced_output, reduced_ops = execute(reduced)
    return EquivalenceReceipt(
        baseline_output=baseline_output,
        reduced_output=reduced_output,
        baseline_operations=baseline_ops,
        reduced_operations=reduced_ops,
        equivalent=baseline_output == reduced_output,
    )
