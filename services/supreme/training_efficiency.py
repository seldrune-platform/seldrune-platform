"""Budget-aware experiment planner for Seldrune STI training research."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OptimizationMethod(StrEnum):
    MIXED_PRECISION = "mixed_precision"
    GRADIENT_ACCUMULATION = "gradient_accumulation"
    ACTIVATION_CHECKPOINTING = "activation_checkpointing"
    ADAPTIVE_RESOLUTION = "adaptive_resolution"
    EARLY_STOPPING = "early_stopping"
    PARAMETER_EFFICIENT_TUNING = "parameter_efficient_tuning"
    DISTILLATION = "distillation"
    DATASET_CURRICULUM = "dataset_curriculum"


@dataclass(frozen=True)
class TrainingBudget:
    usd_limit: float = 10.0
    gpu_hourly_usd: float = 2.10
    reserve_fraction: float = 0.15

    @property
    def usable_usd(self) -> float:
        return self.usd_limit * (1.0 - self.reserve_fraction)

    @property
    def gpu_hour_limit(self) -> float:
        return self.usable_usd / self.gpu_hourly_usd

    def validate(self) -> None:
        if self.usd_limit <= 0 or self.gpu_hourly_usd <= 0:
            raise ValueError("budget and GPU hourly price must be positive")
        if not 0 <= self.reserve_fraction < 1:
            raise ValueError("reserve_fraction must be in [0, 1)")


@dataclass(frozen=True)
class EfficiencyPlan:
    budget: TrainingBudget
    methods: tuple[OptimizationMethod, ...]
    max_experiments: int
    require_baseline: bool = True
    require_quality_gate: bool = True

    def validate(self) -> None:
        self.budget.validate()
        if self.max_experiments < 1:
            raise ValueError("at least one experiment is required")
        if not self.methods:
            raise ValueError("at least one optimization method is required")


def default_sub_10_plan(gpu_hourly_usd: float = 2.10) -> EfficiencyPlan:
    """Research plan: optimize measured quality per GPU-dollar, not promise enterprise parity."""
    plan = EfficiencyPlan(
        budget=TrainingBudget(gpu_hourly_usd=gpu_hourly_usd),
        methods=(
            OptimizationMethod.MIXED_PRECISION,
            OptimizationMethod.GRADIENT_ACCUMULATION,
            OptimizationMethod.ACTIVATION_CHECKPOINTING,
            OptimizationMethod.ADAPTIVE_RESOLUTION,
            OptimizationMethod.EARLY_STOPPING,
            OptimizationMethod.PARAMETER_EFFICIENT_TUNING,
            OptimizationMethod.DISTILLATION,
            OptimizationMethod.DATASET_CURRICULUM,
        ),
        max_experiments=12,
    )
    plan.validate()
    return plan
