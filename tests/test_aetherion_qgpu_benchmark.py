from services.aetherion.qgpu_benchmark import run_universal_benchmark
from services.aetherion.qgpu_model import EvidenceLevel, WorkloadDomain


def test_universal_benchmark_covers_every_qgpu_domain():
    result = run_universal_benchmark()
    assert result.domains == tuple(WorkloadDomain)
    assert len(result.runs) == len(WorkloadDomain)
    assert result.total_input_states > result.total_simulated_states
    assert result.total_eliminated_states > 0
    assert 0 < result.state_reduction_ratio < 1
    assert result.evidence is EvidenceLevel.EXPERIMENTAL
    assert not result.physical_quantum_hardware_verified
    assert not result.hardware_benchmark
