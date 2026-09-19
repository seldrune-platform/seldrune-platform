"""Bridge failed Proof Mesh measurements into queued Forge learning jobs."""

from dataclasses import dataclass

from .experiment_runtime import ExperimentJob
from .feedback_loop import learning_objectives
from .learning_loop import LearningObjective, queue_learning_experiment
from .skill_evolution import Skill
from .verifiers import CheckResult


@dataclass(frozen=True)
class RecoveryPlan:
    skill_id: str
    objectives: tuple[LearningObjective, ...]
    jobs: tuple[ExperimentJob, ...]


def plan_recovery(
    skill: Skill,
    checks: tuple[CheckResult, ...],
    generation: int,
) -> RecoveryPlan:
    if generation < 1:
        raise ValueError("generation must be at least 1")
    objectives = learning_objectives(skill, checks)
    jobs = tuple(
        queue_learning_experiment(objective, generation + index)
        for index, objective in enumerate(objectives)
    )
    return RecoveryPlan(skill.skill_id, objectives, jobs)
