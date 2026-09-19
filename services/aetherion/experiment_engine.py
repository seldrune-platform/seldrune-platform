"""Executable Aetherion strategy experiments.

These experiments measure software transformations only. Results are not GPU
benchmarks and cannot establish hardware performance claims.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ExperimentResult:
    strategy: str
    elapsed_ns: int
    output_digest: str
    operations_avoided: int
    measured: bool = True
    hardware_benchmark: bool = False


def _run(
    strategy: str,
    work: Callable[[], bytes],
    avoided: int = 0,
) -> ExperimentResult:
    started = time.perf_counter_ns()
    output = work()
    elapsed = time.perf_counter_ns() - started
    return ExperimentResult(
        strategy=strategy,
        elapsed_ns=elapsed,
        output_digest=hashlib.sha256(output).hexdigest(),
        operations_avoided=avoided,
    )


def temporal_delta(previous: bytes, current: bytes) -> ExperimentResult:
    if len(previous) != len(current):
        raise ValueError("buffers must have equal length")

    def work() -> bytes:
        return bytes(a ^ b for a, b in zip(previous, current, strict=True))

    unchanged = sum(a == b for a, b in zip(previous, current, strict=True))
    return _run("temporal-delta-execution", work, unchanged)


def predictive_reuse(
    cache: dict[str, bytes],
    key: str,
    compute: Callable[[], bytes],
) -> ExperimentResult:
    hit = key in cache

    def work() -> bytes:
        if hit:
            return cache[key]
        value = compute()
        cache[key] = value
        return value

    return _run("predictive-tensor-reuse", work, int(hit))


def sparse_route(values: tuple[float, ...], threshold: float) -> ExperimentResult:
    active = tuple(value for value in values if abs(value) >= threshold)

    def work() -> bytes:
        return repr(active).encode()

    return _run("adaptive-sparse-routing", work, len(values) - len(active))
