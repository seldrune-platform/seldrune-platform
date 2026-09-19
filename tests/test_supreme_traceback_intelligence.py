import pytest

from services.supreme.traceback_intelligence import (
    TraceNode,
    trace_lineage,
    validate_trace,
)


def test_micro_trace_recovers_task_lineage():
    nodes = (
        TraceNode("root", "build-game", None, ("objective",), 0.9),
        TraceNode("physics", "physics-engine", "root", ("benchmark",), 0.8),
        TraceNode("collision", "collision-test", "physics", ("test-log",), 0.95),
    )
    assert tuple(n.node_id for n in trace_lineage(nodes, "collision")) == (
        "collision",
        "physics",
        "root",
    )


def test_trace_rejects_missing_parent():
    with pytest.raises(ValueError, match="unknown parent"):
        validate_trace((TraceNode("a", "task", "missing"),))


def test_trace_rejects_cycles():
    nodes = (
        TraceNode("a", "task-a", "b"),
        TraceNode("b", "task-b", "a"),
    )
    with pytest.raises(ValueError, match="cycle"):
        validate_trace(nodes)
