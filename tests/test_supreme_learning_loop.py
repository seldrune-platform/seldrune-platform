import pytest

from services.supreme.learning_loop import (
    create_learning_objective,
    queue_learning_experiment,
)
from services.supreme.skill_evolution import Skill


def test_learning_gap_becomes_gpu_experiment():
    objective = create_learning_objective(
        Skill("reasoning", "counterfactual reasoning"),
        "fails long dependency chains",
    )
    job = queue_learning_experiment(objective, 1)
    assert job.experiment_id == "skill-reasoning-g1"
    assert job.accelerator == "rtx-pro-6000-blackwell"
    assert "long dependency chains" in job.hypothesis


def test_learning_gap_is_required():
    with pytest.raises(ValueError, match="gap"):
        create_learning_objective(Skill("vision", "vision reasoning"), "")


def test_generation_is_positive():
    objective = create_learning_objective(
        Skill("research", "research synthesis"),
        "weak source reconciliation",
    )
    with pytest.raises(ValueError, match="generation"):
        queue_learning_experiment(objective, 0)
