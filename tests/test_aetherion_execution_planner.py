from services.aetherion.execution_planner import (
    EvidenceLevel,
    QGPUWorkload,
    WorkloadDomain,
    compile_qgpu_plan,
)


def test_execution_planner_compatibility_points_to_qgpu_model():
    plan = compile_qgpu_plan(QGPUWorkload(WorkloadDomain.AI, 10, 1, 0.5, 0.5))
    assert plan.evidence is EvidenceLevel.HYPOTHETICAL
    assert plan.qir_version == "qir-0.1-hypothesis"
