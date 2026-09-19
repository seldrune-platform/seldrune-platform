from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qir_pipeline_v2 import run_pipeline_v2
from services.aetherion.qir_state_budget import apply_state_budget


def test_pipeline_v2_folds_prunes_and_preserves_output():
    program = QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=6),
            QIROp("b", QIROpcode.CONST, value=4),
            QIROp("sum", QIROpcode.ADD, ("a", "b")),
            QIROp("duplicate", QIROpcode.ADD, ("a", "b")),
            QIROp("dead", QIROpcode.MUL, ("a", "b")),
            QIROp("out", QIROpcode.MUL, ("sum", "duplicate")),
        ),
        "out",
    )
    result = run_pipeline_v2(program)
    assert result.equivalent
    assert result.optimized_output == 100
    assert result.optimized_operations < result.baseline_operations
    assert result.integrity.valid
    assert not result.hardware_benchmark


def test_state_budget_defers_excess_states():
    result = apply_state_budget(1000, 256)
    assert result.admitted_states == 256
    assert result.deferred_states == 744
