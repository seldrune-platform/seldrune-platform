"""Expert Civilization routing for SUPREME execution waves."""

from dataclasses import dataclass
from enum import StrEnum

from .collaboration import ProjectTask


class ExpertKind(StrEnum):
    RESEARCH = "research"
    ENGINEERING = "engineering"
    VERIFICATION = "verification"
    TRAINING = "training"
    MEDIA = "media"


@dataclass(frozen=True)
class ExpertAssignment:
    task_id: str
    expert: ExpertKind


def assign_expert(task: ProjectTask) -> ExpertAssignment:
    text = f"{task.task_id} {task.title}".lower()
    if "proof" in text or "verify" in text or "benchmark" in text:
        expert = ExpertKind.VERIFICATION
    elif "train" in text or "forge" in text:
        expert = ExpertKind.TRAINING
    elif "face" in text or "stream" in text or "mobile" in text:
        expert = ExpertKind.MEDIA
    elif "research" in text or "dataset" in text:
        expert = ExpertKind.RESEARCH
    else:
        expert = ExpertKind.ENGINEERING
    return ExpertAssignment(task.task_id, expert)


def assign_wave(tasks: tuple[ProjectTask, ...]) -> tuple[ExpertAssignment, ...]:
    """Route a ready wave to specialists without serializing independent work."""
    return tuple(assign_expert(task) for task in tasks)
