"""Bridge measured failures into executable Forge learning jobs."""

from dataclasses import dataclass

from .experiment_runtime import ExperimentJob
from .feedback_loop import learning_objectives
from .learning_loop import LearningObjective, queue_learning_experiment
from .skill_evolution import Skill
from .verifiers import CheckResult


@dataclass(frozen=True)
class RecoveryPlan:
    objective: LearningObjective
    job: ExperimentJob


def plan_recovery(
    skill: Skill,
    checks: tuple[CheckResult, ...],
    generation: int,
) -> tuple[RecoveryPlan, ...]:
    """Create one evidence-driven Forge job per failed measured check."""
    objectives = learning_objectives(skill, checks)
    return tuple(
        RecoveryPlan(
            objective,
            queue_learning_experiment(objective, generation),
        )
        for objective in objectives
    )
