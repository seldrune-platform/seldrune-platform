"""Dependency-aware Q-IR partitioning experiment."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram


@dataclass(frozen=True)
class PartitionReceipt:
    layers: tuple[tuple[str, ...], ...]
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    distributed_hardware_verified: bool = False


def partition_dependency_layers(program: QIRProgram) -> PartitionReceipt:
    pending = {op.op_id: set(op.inputs) for op in program.operations}
    done: set[str] = set()
    layers: list[tuple[str, ...]] = []
    while pending:
        ready = tuple(sorted(key for key, deps in pending.items() if deps <= done))
        if not ready:
            raise ValueError("Q-IR graph contains missing dependencies or a cycle")
        layers.append(ready)
        done.update(ready)
        for key in ready:
            del pending[key]
    return PartitionReceipt(tuple(layers))
