from services.aetherion.qgpu_engine_v2 import execute
from services.aetherion.qgpu_validation import validate
from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.qmemory_v2 import QMemoryV2


def test_integrated_qgpu_engine_reduces_and_validates():
    program = QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=5),
            QIROp("b", QIROpcode.CONST, value=5),
            QIROp("x", QIROpcode.ADD, ("a", "b")),
            QIROp("y", QIROpcode.ADD, ("b", "a")),
            QIROp("out", QIROpcode.MUL, ("x", "y")),
        ),
        "out",
    )
    receipt = execute(program)
    assert receipt.field.equivalent
    assert receipt.field.eliminated_states > 0
    assert validate(receipt).accepted
    assert not receipt.quantum_speedup_verified


def test_qmemory_v2_is_bounded_and_tracks_evidence():
    memory = QMemoryV2(capacity=2)
    memory.put("a", b"1")
    memory.put("b", b"2")
    assert memory.get("a") == b"1"
    memory.put("c", b"3")
    assert memory.get("b") is None
    receipt = memory.receipt()
    assert receipt.hits == 1
    assert receipt.misses == 1
    assert receipt.evictions == 1
