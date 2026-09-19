"""Timing receipt for concurrent QNode software experiments."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qnode_runtime import execute


@dataclass(frozen=True)
class QNodeBenchmarkReceipt:
    elapsed_ns: int
    node_count: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_benchmark: bool = False
    quantum_speedup_verified: bool = False


def benchmark(program: QIRProgram) -> QNodeBenchmarkReceipt:
    start = perf_counter_ns()
    result = execute(program)
    return QNodeBenchmarkReceipt(
        perf_counter_ns() - start,
        len(result.fabric.reports),
    )
