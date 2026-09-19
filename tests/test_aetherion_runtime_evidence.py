from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.runtime_evidence import collect_runtime_evidence


def test_runtime_evidence_separates_software_from_quantum_hardware():
    program = QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=7),
            QIROp("b", QIROpcode.CONST, value=5),
            QIROp("out", QIROpcode.ADD, ("a", "b")),
        ),
        "out",
    )
    result = collect_runtime_evidence(program)
    assert result.software_pipeline_verified
    assert result.qnode_consensus_verified
    assert not result.physical_quantum_hardware_verified
    assert not result.quantum_speedup_verified
    assert len(result.report_sha256) == 64
