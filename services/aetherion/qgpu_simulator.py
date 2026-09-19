"""Aetherion QGPU execution-field simulator.

The simulator explores the invented QGPU model on classical software. Its
measurements describe this simulator only and are not quantum-hardware results.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from .qgpu_model import EvidenceLevel, QGPUPlan


@dataclass(frozen=True)
class QGPUSimulationReceipt:
    qir_version: str
    input_states: int
    simulated_states: int
    eliminated_states: int
    elapsed_ns: int
    result_digest: str
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False
    hardware_benchmark: bool = False


def simulate_execution_field(
    plan: QGPUPlan,
    payload: bytes,
) -> QGPUSimulationReceipt:
    if not payload:
        raise ValueError("simulation payload is required")

    field = plan.execution_field
    started = time.perf_counter_ns()

    # Deterministic classical stand-in for execution of surviving QEF states.
    seed = hashlib.sha256(payload).digest()
    state = seed
    for index in range(field.surviving_states):
        state = hashlib.sha256(state + index.to_bytes(8, "big")).digest()

    elapsed = time.perf_counter_ns() - started
    return QGPUSimulationReceipt(
        qir_version=plan.qir_version,
        input_states=field.candidate_states,
        simulated_states=field.surviving_states,
        eliminated_states=field.reducible_states,
        elapsed_ns=elapsed,
        result_digest=state.hex(),
    )
