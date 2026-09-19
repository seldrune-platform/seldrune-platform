"""Parallelism envelope estimation from Q-IR dependency layers."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_partition import partition_dependency_layers


@dataclass(frozen=True)
class ParallelismReceipt:
    depth: int
    peak_parallel_operations: int
    average_parallel_operations: float
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_speedup_verified: bool = False


def estimate_parallelism(program: QIRProgram) -> ParallelismReceipt:
    layers = partition_dependency_layers(program).layers
    sizes = [len(layer) for layer in layers]
    return ParallelismReceipt(
        len(layers),
        max(sizes, default=0),
        sum(sizes) / len(sizes) if sizes else 0.0,
    )
