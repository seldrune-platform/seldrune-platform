"""Tests for the Seldrune SUPREME v0.1 execution policy."""

import pytest

from services.supreme.core import CognitiveMode, Objective, plan_execution


def test_fast_mode_enables_speculation_without_forcing_verification():
    policy = plan_execution(Objective("build application", max_parallelism=8))
    assert policy.parallelism == 8
    assert policy.speculative_execution is True
    assert policy.require_verification is False


def test_accuracy_critical_work_requires_verification():
    policy = plan_execution(
        Objective("validate result", accuracy_critical=True, max_parallelism=2)
    )
    assert policy.require_verification is True


def test_research_mode_preserves_provenance_and_verifies():
    policy = plan_execution(
        Objective("discover architecture", mode=CognitiveMode.RESEARCH)
    )
    assert policy.require_verification is True
    assert policy.speculative_execution is True
    assert policy.preserve_provenance is True


@pytest.mark.parametrize(
    "objective",
    [Objective(""), Objective("work", max_parallelism=0)],
)
def test_invalid_objectives_are_rejected(objective):
    with pytest.raises(ValueError):
        plan_execution(objective)
