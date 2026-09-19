"""Aetherion probabilistic dependency scheduler experiment."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class QTask:
    task_id: str
    dependencies: tuple[str, ...] = ()
    probability: float = 1.0


@dataclass(frozen=True)
class QSchedule:
    order: tuple[str, ...]
    speculative: tuple[str, ...]
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False


def schedule(tasks: tuple[QTask, ...], speculative_threshold: float = 0.75) -> QSchedule:
    by_id = {task.task_id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("task ids must be unique")
    for task in tasks:
        if not 0 <= task.probability <= 1:
            raise ValueError("probability must be normalized")
        if any(dep not in by_id for dep in task.dependencies):
            raise ValueError("unknown dependency")

    done: set[str] = set()
    order: list[str] = []
    while len(done) < len(tasks):
        ready = [
            task
            for task in tasks
            if task.task_id not in done
            and all(dep in done for dep in task.dependencies)
        ]
        if not ready:
            raise ValueError("dependency graph contains a cycle")
        ready.sort(key=lambda task: (-task.probability, task.task_id))
        for task in ready:
            order.append(task.task_id)
            done.add(task.task_id)

    speculative = tuple(
        task.task_id
        for task in tasks
        if task.probability >= speculative_threshold
    )
    return QSchedule(tuple(order), speculative)
