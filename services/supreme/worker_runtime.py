"""Executable work contracts for STI and LiveShift workers."""

from dataclasses import dataclass
from enum import StrEnum

from .collaboration import ProjectTask
from .experts import ExpertKind, assign_expert


class ResourceKind(StrEnum):
    CPU = "cpu"
    GPU = "gpu"


@dataclass(frozen=True)
class WorkOrder:
    task_id: str
    title: str
    expert: ExpertKind
    resource: ResourceKind
    accelerator: str | None


@dataclass(frozen=True)
class WorkResult:
    task_id: str
    succeeded: bool
    evidence: tuple[str, ...]
    error: str | None = None


def dispatch_order(task: ProjectTask) -> WorkOrder:
    assignment = assign_expert(task)
    gpu = assignment.expert in {ExpertKind.TRAINING, ExpertKind.MEDIA}
    return WorkOrder(
        task_id=task.task_id,
        title=task.title,
        expert=assignment.expert,
        resource=ResourceKind.GPU if gpu else ResourceKind.CPU,
        accelerator="rtx-pro-6000-blackwell" if gpu else None,
    )


def validate_result(result: WorkResult) -> None:
    if result.succeeded and not result.evidence:
        raise ValueError("successful work requires evidence")
    if not result.succeeded and not result.error:
        raise ValueError("failed work requires an error")
