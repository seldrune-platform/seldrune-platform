import pytest

from services.supreme.collaboration import ProjectTask
from services.supreme.hyperspeed import build_execution_waves, propagate_failure


def test_hyperspeed_parallelizes_independent_tasks():
    tasks = (
        ProjectTask("inventory", "Inventory system"),
        ProjectTask("bench", "Benchmark baseline"),
        ProjectTask("router", "Build router", ("inventory",)),
        ProjectTask("integrate", "Integrate", ("router", "bench")),
    )
    waves = build_execution_waves(tasks)
    assert waves[0].task_ids == ("bench", "inventory")
    assert waves[1].task_ids == ("router",)
    assert waves[2].task_ids == ("integrate",)


def test_cycle_is_rejected():
    tasks = (
        ProjectTask("a", "A", ("b",)),
        ProjectTask("b", "B", ("a",)),
    )
    with pytest.raises(ValueError, match="cyclic"):
        build_execution_waves(tasks)


def test_unknown_dependency_is_rejected():
    with pytest.raises(ValueError, match="unknown dependencies"):
        build_execution_waves((ProjectTask("a", "A", ("missing",)),))


def test_failure_propagates_to_dependents_only():
    tasks = (
        ProjectTask("a", "A"),
        ProjectTask("b", "B", ("a",)),
        ProjectTask("c", "C"),
        ProjectTask("d", "D", ("b",)),
    )
    assert propagate_failure(tasks, "a") == frozenset({"a", "b", "d"})
