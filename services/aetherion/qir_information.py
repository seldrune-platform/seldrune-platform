"""Information-flow accounting for Aetherion Q-IR research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram


@dataclass(frozen=True)
class InformationReceipt:
    operation_nodes: int
    dependency_edges: int
    fanout_edges: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False


def analyze_information_flow(program: QIRProgram) -> InformationReceipt:
    edges = sum(len(op.inputs) for op in program.operations)
    uses: dict[str, int] = {}
    for op in program.operations:
        for item in op.inputs:
            uses[item] = uses.get(item, 0) + 1
    fanout = sum(max(0, count - 1) for count in uses.values())
    return InformationReceipt(len(program.operations), edges, fanout)
