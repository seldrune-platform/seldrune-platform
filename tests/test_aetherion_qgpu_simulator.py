from services.aetherion.qgpu_model import (
    EvidenceLevel,
    QGPUWorkload,
    WorkloadDomain,
    compile_qgpu_plan,
)
from services.aetherion.qgpu_simulator import simulate_execution_field


def test_qgpu_simulator_promotes_only_simulation_to_experimental():
    plan = compile_qgpu_plan(
        QGPUWorkload(WorkloadDomain.AI, 100, 20, 0.6, 0.4)
    )
    receipt = simulate_execution_field(plan, b"universal-workload")
    assert receipt.evidence is EvidenceLevel.EXPERIMENTAL
    assert receipt.input_states == 100
    assert receipt.simulated_states == 50
    assert receipt.eliminated_states == 50
    assert not receipt.physical_quantum_hardware_verified
    assert not receipt.hardware_benchmark


def test_qgpu_simulation_is_deterministic_for_same_plan_and_payload():
    plan = compile_qgpu_plan(
        QGPUWorkload(WorkloadDomain.SIMULATION, 20, 5, 0.2, 0.2)
    )
    first = simulate_execution_field(plan, b"physics")
    second = simulate_execution_field(plan, b"physics")
    assert first.result_digest == second.result_digest


def test_qgpu_simulator_rejects_empty_payload():
    plan = compile_qgpu_plan(
        QGPUWorkload(WorkloadDomain.MEDIA, 10, 1, 0, 0)
    )
    try:
        simulate_execution_field(plan, b"")
    except ValueError as exc:
        assert str(exc) == "simulation payload is required"
    else:
        raise AssertionError("empty payload must fail")
