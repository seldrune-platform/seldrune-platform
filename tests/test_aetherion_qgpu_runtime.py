from services.aetherion.qgpu_memory import QMemory
from services.aetherion.qgpu_model import (
    EvidenceLevel,
    QGPUWorkload,
    WorkloadDomain,
)
from services.aetherion.qgpu_runtime import execute_qgpu_simulation


def test_integrated_qgpu_runtime_produces_experimental_receipt():
    result = execute_qgpu_simulation(
        QGPUWorkload(WorkloadDomain.AI, 100, 10, 0.6, 0.4),
        b"model-workload",
    )
    assert result.evidence is EvidenceLevel.EXPERIMENTAL
    assert result.simulation.eliminated_states == 50
    assert result.schedule.order[-1] == "result-verify"
    assert not result.physical_quantum_hardware_verified
    assert not result.hardware_benchmark


def test_integrated_runtime_reuses_qmemory_between_jobs():
    memory = QMemory()
    workload = QGPUWorkload(WorkloadDomain.MEDIA, 20, 4, 0.5, 0.3)
    first = execute_qgpu_simulation(workload, b"frame-state", memory=memory)
    second = execute_qgpu_simulation(workload, b"frame-state", memory=memory)
    assert first.memory.hits == 0
    assert second.memory.hits == 1
    assert second.memory.reuse_ratio == 0.5
    assert first.simulation.result_digest == second.simulation.result_digest
