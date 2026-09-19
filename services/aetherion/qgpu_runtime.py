"""Integrated Aetherion QGPU simulation runtime.

Executes the research QGPU plan through Q-Memory and the probabilistic
dependency scheduler. This remains a classical simulation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_memory import QMemory, QMemoryReceipt, receipt
from .qgpu_model import EvidenceLevel, QGPUWorkload, compile_qgpu_plan
from .qgpu_scheduler import QSchedule, QTask, schedule
from .qgpu_simulator import QGPUSimulationReceipt, simulate_execution_field


@dataclass(frozen=True)
class QGPURuntimeReceipt:
    simulation: QGPUSimulationReceipt
    memory: QMemoryReceipt
    schedule: QSchedule
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False
    hardware_benchmark: bool = False


def execute_qgpu_simulation(
    workload: QGPUWorkload,
    payload: bytes,
    *,
    memory: QMemory | None = None,
) -> QGPURuntimeReceipt:
    plan = compile_qgpu_plan(workload)
    qmemory = memory if memory is not None else QMemory()
    resolved, _ = qmemory.resolve(payload)

    tasks = (
        QTask("qir-compile", probability=1.0),
        QTask("q-memory-resolve", ("qir-compile",), 0.98),
        QTask("qef-state-reduction", ("q-memory-resolve",), 0.95),
        QTask("qef-execute", ("qef-state-reduction",), 0.9),
        QTask("result-verify", ("qef-execute",), 1.0),
    )
    qschedule = schedule(tasks)
    simulation = simulate_execution_field(plan, resolved)
    return QGPURuntimeReceipt(
        simulation=simulation,
        memory=receipt(qmemory),
        schedule=qschedule,
    )
