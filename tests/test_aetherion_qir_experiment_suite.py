from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qir_equivalence import reduce_common_subexpressions
from services.aetherion.qir_experiment_suite import run_experiment_suite


def test_commutative_expressions_reduce_to_one_state():
    program = QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=8),
            QIROp("b", QIROpcode.CONST, value=3),
            QIROp("x", QIROpcode.ADD, ("a", "b")),
            QIROp("y", QIROpcode.ADD, ("b", "a")),
            QIROp("out", QIROpcode.MUL, ("x", "y")),
        ),
        "out",
    )
    reduced = reduce_common_subexpressions(program)
    assert len(reduced.operations) == 4


def test_experiment_suite_is_reproducible_and_evidence_gated():
    program = QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=2),
            QIROp("b", QIROpcode.CONST, value=9),
            QIROp("out", QIROpcode.MUL, ("a", "b")),
        ),
        "out",
    )
    first = run_experiment_suite(program)
    second = run_experiment_suite(program)
    assert first.pipeline.equivalent
    assert first.checkpoint.program_sha256 == second.checkpoint.program_sha256
    assert first.parallelism.peak_parallel_operations == 2
    assert not first.physical_quantum_hardware_verified
    assert not first.quantum_speedup_verified
