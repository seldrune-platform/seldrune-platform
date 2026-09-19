"""HyperSpeed dependency scheduler for Seldrune SUPREME."""

from dataclasses import dataclass
from enum import StrEnum

from .collaboration import ProjectTask


class TaskOutcome(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExecutionWave:
    task_ids: tuple[str, ...]


def build_execution_waves(tasks: tuple[ProjectTask, ...]) -> tuple[ExecutionWave, ...]:
    """Create deterministic parallel waves while respecting dependencies."""
    by_id = {task.task_id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("task ids must be unique")

    known = set(by_id)
    for task in tasks:
        missing = set(task.dependencies) - known
        if missing:
            raise ValueError(f"unknown dependencies for {task.task_id}: {sorted(missing)}")

    completed: set[str] = set()
    waves: list[ExecutionWave] = []
    while len(completed) < len(tasks):
        ready = sorted(
            task.task_id
            for task in tasks
            if task.task_id not in completed
            and all(dep in completed for dep in task.dependencies)
        )
        if not ready:
            raise ValueError("cyclic task dependencies")
        waves.append(ExecutionWave(tuple(ready)))
        completed.update(ready)
    return tuple(waves)


def propagate_failure(
    tasks: tuple[ProjectTask, ...], failed_task_id: str
) -> frozenset[str]:
    """Find work that cannot run after a prerequisite fails."""
    blocked = {failed_task_id}
    changed = True
    while changed:
        changed = False
        for task in tasks:
            if task.task_id not in blocked and any(
                dep in blocked for dep in task.dependencies
            ):
                blocked.add(task.task_id)
                changed = True
    return frozenset(blocked)
