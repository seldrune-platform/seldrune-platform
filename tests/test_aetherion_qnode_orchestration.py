from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qnode_faults import classify
from services.aetherion.qnode_orchestrator import orchestrate
from services.aetherion.qnode_release_gate import evaluate


def sample_program():
    return QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=2),
            QIROp("b", QIROpcode.CONST, value=3),
            QIROp("out", QIROpcode.ADD, ("a", "b")),
        ),
        "out",
    )


def test_orchestration_is_deterministic_and_evidence_gated():
    first = orchestrate(sample_program())
    second = orchestrate(sample_program())
    assert first.report_sha256 == second.report_sha256
    gate = evaluate(first)
    assert gate.software_verified
    assert not gate.physical_quantum_verified
    assert not first.autonomous_background_execution


def test_fault_classification_isolated():
    receipt = classify({"a": 1, "b": RuntimeError("boom")})
    assert receipt.succeeded == ("a",)
    assert receipt.failed == ("b",)
