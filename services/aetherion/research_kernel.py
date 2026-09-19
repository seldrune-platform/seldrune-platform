"""Aetherion universal-factor research kernel.

Scores candidate execution strategies without pretending simulated scores are
hardware benchmarks. The kernel is backend-neutral: physical accelerators are
optional adapters, not part of the Aetherion identity.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniversalFactors:
    latency: float
    memory_motion: float
    energy: float
    parallelism: float
    reuse: float
    sparsity: float
    locality: float
    precision_cost: float

    def validate(self) -> None:
        for value in self.__dict__.values():
            if not 0.0 <= value <= 1.0:
                raise ValueError("universal factors must be normalized to 0..1")


@dataclass(frozen=True)
class StrategyScore:
    name: str
    experimental_score: float
    measured: bool = False


def score_strategy(name: str, factors: UniversalFactors) -> StrategyScore:
    factors.validate()
    cost = (
        factors.latency
        + factors.memory_motion
        + factors.energy
        + factors.precision_cost
    ) / 4
    opportunity = (
        factors.parallelism
        + factors.reuse
        + factors.sparsity
        + factors.locality
    ) / 4
    score = max(0.0, min(1.0, opportunity * (1.0 - cost)))
    return StrategyScore(name=name, experimental_score=score, measured=False)


def candidate_strategies() -> tuple[str, ...]:
    return (
        "temporal-delta-execution",
        "predictive-tensor-reuse",
        "adaptive-sparse-routing",
        "distributed-memory-locality",
        "mixed-precision-cascade",
        "speculative-parallel-branches",
        "quantum-inspired-schedule-search",
        "workload-specific-kernel-fusion",
    )
