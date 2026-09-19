"""Aetherion experimental execution planner.

Ranks software execution plans from observable workload properties. Planner
scores are decision heuristics, never hardware benchmark results.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadProfile:
    temporal_similarity: float
    sparsity: float
    locality: float
    parallel_fraction: float
    fusion_opportunity: float

    def validate(self) -> None:
        for value in self.__dict__.values():
            if not 0.0 <= value <= 1.0:
                raise ValueError("workload properties must be normalized to 0..1")


@dataclass(frozen=True)
class ExecutionPlan:
    strategies: tuple[str, ...]
    heuristic_score: float
    measured: bool = False
    hardware_benchmark: bool = False


def build_plan(profile: WorkloadProfile) -> ExecutionPlan:
    profile.validate()
    candidates = (
        ("temporal-delta-execution", profile.temporal_similarity),
        ("predictive-tensor-reuse", profile.temporal_similarity * profile.locality),
        ("adaptive-sparse-routing", profile.sparsity),
        ("distributed-memory-locality", profile.locality),
        ("workload-specific-kernel-fusion", profile.fusion_opportunity),
        ("speculative-parallel-branches", profile.parallel_fraction),
        (
            "quantum-inspired-schedule-search",
            (profile.parallel_fraction + profile.fusion_opportunity) / 2,
        ),
    )
    ranked = sorted(candidates, key=lambda item: (-item[1], item[0]))
    selected = tuple(name for name, score in ranked if score >= 0.5)
    heuristic = sum(score for _, score in ranked[:3]) / 3
    return ExecutionPlan(selected, round(heuristic, 6))


def live_media_profile(
    *,
    temporal_similarity: float,
    sparsity: float,
    locality: float,
) -> WorkloadProfile:
    return WorkloadProfile(
        temporal_similarity=temporal_similarity,
        sparsity=sparsity,
        locality=locality,
        parallel_fraction=0.8,
        fusion_opportunity=0.8,
    )
