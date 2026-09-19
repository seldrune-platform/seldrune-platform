from services.aetherion.qgpu_memory import QMemory, receipt
from services.aetherion.qgpu_scheduler import QTask, schedule


def test_qmemory_reuses_identical_information_state():
    memory = QMemory()
    _, first_hit = memory.resolve(b"tensor-state")
    _, second_hit = memory.resolve(b"tensor-state")
    evidence = receipt(memory)
    assert not first_hit
    assert second_hit
    assert evidence.hits == 1
    assert evidence.misses == 1
    assert evidence.reuse_ratio == 0.5
    assert not evidence.hardware_benchmark


def test_scheduler_respects_dependencies_and_marks_speculation():
    result = schedule(
        (
            QTask("decode", probability=0.9),
            QTask("infer", ("decode",), 0.95),
            QTask("render", ("infer",), 0.8),
        )
    )
    assert result.order == ("decode", "infer", "render")
    assert result.speculative == ("decode", "infer", "render")
    assert not result.physical_quantum_hardware_verified


def test_scheduler_rejects_cycles():
    try:
        schedule((QTask("a", ("b",)), QTask("b", ("a",))))
    except ValueError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("cycle must fail")
