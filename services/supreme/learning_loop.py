"""STI learning loop connecting skill discovery to Forge experiments."""

from dataclasses import dataclass

from .experiment_runtime import ExperimentJob, queue_experiment
from .forge import next_experiment
from .skill_evolution import Skill


@dataclass(frozen=True)
class LearningObjective:
    skill_id: str
    gap: str
    hypothesis: str


def create_learning_objective(skill: Skill, gap: str) -> LearningObjective:
    if not gap.strip():
        raise ValueError("learning gap is required")
    hypothesis = (
        f"Improve {skill.description} by addressing measured capability gap: {gap}"
    )
    return LearningObjective(skill.skill_id, gap, hypothesis)


def queue_learning_experiment(
    objective: LearningObjective,
    generation: int,
) -> ExperimentJob:
    if generation < 1:
        raise ValueError("generation must be at least 1")
    experiment = next_experiment(
        f"skill-{objective.skill_id}-g{generation}",
        objective.hypothesis,
    )
    return queue_experiment(experiment)
