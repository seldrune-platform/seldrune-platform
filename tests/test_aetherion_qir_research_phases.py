from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qir_pruning import prune_dead_states
from services.aetherion.qir_research import run_qir_research
from services.aetherion.qir_reversible import analyze_reversibility
from services.aetherion.qir_schedule_search import (
    ScheduleCandidate,
    search_schedule,
)
from services.aetherion.qir_verifier import optimize_and_verify


def sample_program():
    return QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=5),
            QIROp("b", QIROpcode.CONST, value=2),
            QIROp("sum1", QIROpcode.ADD, ("a", "b")),
            QIROp("sum2", QIROpcode.ADD, ("a", "b")),
            QIROp("dead", QIROpcode.MUL, ("a", "b")),
            QIROp("out", QIROpcode.XOR, ("sum1", "sum2")),
        ),
        "out",
    )


def test_phase_1_reversible_accounting():
    result = analyze_reversibility(sample_program())
    assert result.logically_reversible_operations == 1
    assert not result.physical_quantum_hardware_verified


def test_phase_2_dead_state_pruning():
    result = prune_dead_states(sample_program())
    assert "dead" not in {op.op_id for op in result.operations}


def test_phase_3_composite_optimizer_preserves_result():
    result = optimize_and_verify(sample_program())
    assert result.equivalent
    assert result.operations_eliminated >= 2
    assert not result.hardware_benchmark


def test_phase_4_schedule_search_uses_cost_model():
    result = search_schedule(
        (
            ScheduleCandidate("memory-heavy", 20, 1, 10),
            ScheduleCandidate("balanced", 5, 2, 12),
            ScheduleCandidate("sync-heavy", 4, 10, 12),
        )
    )
    assert result.selected.name == "balanced"
    assert not result.quantum_speedup_verified


def test_phase_5_unified_research_receipt_stays_experimental():
    result = run_qir_research(sample_program())
    assert result.verification.equivalent
    assert not result.physical_quantum_hardware_verified
    assert not result.quantum_speedup_verified
