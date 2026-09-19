"""Tests for STI budget-aware training efficiency research engine."""
import pytest

from services.supreme.training_efficiency import (
    OptimizationMethod,
    TrainingBudget,
    default_sub_10_plan,
)


def test_default_plan_respects_ten_dollar_cap() -> None:
    plan = default_sub_10_plan()
    assert plan.budget.usd_limit == 10.0
    assert plan.budget.usable_usd == pytest.approx(8.5)
    assert plan.budget.gpu_hour_limit == pytest.approx(8.5 / 2.10)
    assert plan.require_baseline is True
    assert plan.require_quality_gate is True


def test_default_plan_has_efficiency_search_methods() -> None:
    plan = default_sub_10_plan()
    assert OptimizationMethod.MIXED_PRECISION in plan.methods
    assert OptimizationMethod.EARLY_STOPPING in plan.methods
    assert OptimizationMethod.PARAMETER_EFFICIENT_TUNING in plan.methods
    assert OptimizationMethod.DATASET_CURRICULUM in plan.methods


def test_budget_validation_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        TrainingBudget(usd_limit=0).validate()
    with pytest.raises(ValueError):
        TrainingBudget(gpu_hourly_usd=0).validate()
    with pytest.raises(ValueError):
        TrainingBudget(reserve_fraction=1.0).validate()


def test_custom_gpu_price_changes_hour_limit() -> None:
    plan = default_sub_10_plan(gpu_hourly_usd=1.0)
    assert plan.budget.gpu_hour_limit == pytest.approx(8.5)
