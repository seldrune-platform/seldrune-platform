"""Bridge failed measured checks into queued Forge learning experiments."""

from dataclasses import dataclass

from .experiment_runtime import ExperimentJob
from .feedback_loop import learning_objectives
from .learning_loop import queue_learning_experiment
from .skill_evolution import Skill
from .verifiers import CheckResult


@dataclass(frozen=True)
class LearningCycle:
    skill_id: str
    generation: int
    jobs: tuple[ExperimentJob, ...]


def plan_learning_cycle(
    skill: Skill,
    checks: tuple[CheckResult, ...],
    generation: int,
) -> LearningCycle:
    if generation < 1:
        raise ValueError("generation must be at least 1")
    objectives = learning_objectives(skill, checks)
    jobs = tuple(
        queue_learning_experiment(objective, generation)
        for objective in objectives
    )
    return LearningCycle(skill.skill_id, generation, jobs)
