from services.aetherion.qgpu_model import (
    EvidenceLevel,
    QGPUWorkload,
    WorkloadDomain,
    compile_qgpu_plan,
)


def test_qgpu_plan_is_explicitly_hypothetical():
    workload = QGPUWorkload(WorkloadDomain.AI, 1000, 50, 0.6, 0.4)
    plan = compile_qgpu_plan(workload)
    assert plan.evidence is EvidenceLevel.HYPOTHETICAL
    assert not plan.physical_quantum_hardware_verified
    assert plan.execution_field.surviving_states == 500


def test_qgpu_accepts_universal_workload_domains():
    for domain in WorkloadDomain:
        plan = compile_qgpu_plan(QGPUWorkload(domain, 10, 1, 0, 0))
        assert plan.domain is domain


def test_qgpu_never_self_promotes_to_verified():
    plan = compile_qgpu_plan(
        QGPUWorkload(WorkloadDomain.SCIENTIFIC, 100, 20, 1, 1)
    )
    assert plan.evidence is not EvidenceLevel.VERIFIED
    assert plan.execution_field.evidence is EvidenceLevel.HYPOTHETICAL
