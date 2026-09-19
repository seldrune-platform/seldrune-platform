"""Universal workload benchmark harness for the Aetherion QGPU simulator.

Results are measurements of the classical research simulator, never claims of
physical quantum speedup or accelerator performance.
"""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_memory import QMemory
from .qgpu_model import EvidenceLevel, QGPUWorkload, WorkloadDomain
from .qgpu_runtime import QGPURuntimeReceipt, execute_qgpu_simulation


@dataclass(frozen=True)
class UniversalBenchmarkReceipt:
    runs: tuple[QGPURuntimeReceipt, ...]
    domains: tuple[WorkloadDomain, ...]
    total_input_states: int
    total_simulated_states: int
    total_eliminated_states: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False
    hardware_benchmark: bool = False

    @property
    def state_reduction_ratio(self) -> float:
        if not self.total_input_states:
            return 0.0
        return self.total_eliminated_states / self.total_input_states


def run_universal_benchmark() -> UniversalBenchmarkReceipt:
    memory = QMemory()
    runs: list[QGPURuntimeReceipt] = []
    domains = tuple(WorkloadDomain)
    for index, domain in enumerate(domains):
        workload = QGPUWorkload(
            domain=domain,
            state_space=100 + index * 20,
            dependency_edges=10 + index,
            reusable_fraction=min(0.2 + index * 0.08, 0.8),
            sparse_fraction=min(0.3 + index * 0.06, 0.8),
        )
        payload = f"aetherion:{domain.value}:reference-workload".encode()
        runs.append(execute_qgpu_simulation(workload, payload, memory=memory))

    return UniversalBenchmarkReceipt(
        runs=tuple(runs),
        domains=domains,
        total_input_states=sum(r.simulation.input_states for r in runs),
        total_simulated_states=sum(r.simulation.simulated_states for r in runs),
        total_eliminated_states=sum(r.simulation.eliminated_states for r in runs),
    )
