from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qnode_benchmark import benchmark
from services.aetherion.qnode_runtime import execute


def program():
    return QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=4),
            QIROp("b", QIROpcode.CONST, value=6),
            QIROp("x", QIROpcode.ADD, ("a", "b")),
            QIROp("out", QIROpcode.MUL, ("x", "b")),
        ),
        "out",
    )


def test_qnodes_report_together_and_reach_software_consensus():
    result = execute(program())
    assert len(result.fabric.reports) == 5
    assert result.fabric.all_completed
    assert result.consensus.accepted
    assert not result.physical_quantum_nodes_verified


def test_qnode_benchmark_does_not_claim_quantum_speedup():
    result = benchmark(program())
    assert result.node_count == 5
    assert result.elapsed_ns >= 0
    assert not result.hardware_benchmark
    assert not result.quantum_speedup_verified
