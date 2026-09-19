"""Cross-domain software benchmark for Aetherion research kernels."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns

from .qgpu_kernels import KernelKind, run_kernel
from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class BenchmarkCase:
    kernel: KernelKind
    elapsed_ns: int
    operations: int


@dataclass(frozen=True)
class BenchmarkV2Receipt:
    cases: tuple[BenchmarkCase, ...]
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_benchmark: bool = False
    quantum_speedup_verified: bool = False


def run_benchmark(size: int = 256) -> BenchmarkV2Receipt:
    left = tuple(float(i) for i in range(size))
    right = tuple(float(size - i) for i in range(size))
    cases = []
    for kind in KernelKind:
        start = perf_counter_ns()
        result = run_kernel(kind, left, right)
        cases.append(BenchmarkCase(kind, perf_counter_ns() - start, result.operations))
    return BenchmarkV2Receipt(tuple(cases))
