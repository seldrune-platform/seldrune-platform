from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qir_batch import run_qir_batch
from services.aetherion.qir_cost import ExecutionCost, compare_costs
from services.aetherion.qir_precision import select_precision


def program():
    return QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=4),
            QIROp("b", QIROpcode.CONST, value=2),
            QIROp("x", QIROpcode.ADD, ("a", "b")),
            QIROp("y", QIROpcode.MUL, ("x", "b")),
        ),
        "y",
    )


def test_information_and_dependency_partition_batch():
    result = run_qir_batch(program())
    assert result.information.dependency_edges == 4
    assert result.partition.layers == (("a", "b"), ("x",), ("y",))
    assert result.research.verification.equivalent
    assert not result.physical_quantum_hardware_verified


def test_multi_objective_cost_receipt_is_not_hardware_benchmark():
    result = compare_costs(
        ExecutionCost(100, 50, 10, 2),
        ExecutionCost(80, 20, 8, 1),
    )
    assert result.improvement > 0
    assert not result.hardware_benchmark


def test_precision_policy_respects_minimum():
    result = select_precision(16, 32)
    assert result.selected_bits == 32
