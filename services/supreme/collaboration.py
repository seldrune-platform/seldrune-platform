"""Collaboration contract between Seldrune SUPREME and an external builder.

SUPREME can inspect project state, propose work, execute approved task classes,
test results, and return evidence. Production promotion remains separately gated.
"""

from dataclasses import dataclass
from enum import StrEnum


class WorkState(StrEnum):
    DISCOVERED = "discovered"
    READY = "ready"
    RUNNING = "running"
    VERIFIED = "verified"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ProjectTask:
    task_id: str
    title: str
    dependencies: tuple[str, ...] = ()
    state: WorkState = WorkState.DISCOVERED


def ready_tasks(
    tasks: tuple[ProjectTask, ...], completed: frozenset[str]
) -> tuple[ProjectTask, ...]:
    """Expose all dependency-satisfied work for parallel execution."""
    return tuple(
        task
        for task in tasks
        if task.task_id not in completed
        and all(dep in completed for dep in task.dependencies)
    )


def completion_ratio(tasks: tuple[ProjectTask, ...], completed: frozenset[str]) -> float:
    if not tasks:
        return 1.0
    done = sum(task.task_id in completed for task in tasks)
    return done / len(tasks)
