from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qir_equivalence import verify_equivalence


def test_qir_common_subexpression_reduction_preserves_output():
    program = QIRProgram(
        operations=(
            QIROp("a", QIROpcode.CONST, value=7),
            QIROp("b", QIROpcode.CONST, value=3),
            QIROp("sum1", QIROpcode.ADD, ("a", "b")),
            QIROp("sum2", QIROpcode.ADD, ("a", "b")),
            QIROp("out", QIROpcode.MUL, ("sum1", "sum2")),
        ),
        output_id="out",
    )
    result = verify_equivalence(program)
    assert result.equivalent
    assert result.baseline_output == 100
    assert result.reduced_output == 100
    assert result.reduced_operations < result.baseline_operations
    assert not result.physical_quantum_hardware_verified
