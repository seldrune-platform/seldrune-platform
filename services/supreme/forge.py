"""Seldrune Forge: bounded recursive AGI research/training controller.

Forge proposes candidate improvements and promotes none automatically. Candidates
must beat the active baseline on declared metrics before owner-controlled release.
"""

from dataclasses import dataclass
from enum import StrEnum


class ExperimentState(StrEnum):
    PROPOSED = "proposed"
    TRAINING = "training"
    REJECTED = "rejected"
    CANDIDATE = "candidate"


@dataclass(frozen=True)
class Benchmark:
    accuracy: float
    task_success: float
    latency_ms: float
    gpu_seconds: float


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    hypothesis: str
    state: ExperimentState = ExperimentState.PROPOSED


def candidate_beats_baseline(candidate: Benchmark, baseline: Benchmark) -> bool:
    """Require quality gains without regressions in efficiency."""
    return (
        candidate.accuracy >= baseline.accuracy
        and candidate.task_success >= baseline.task_success
        and candidate.latency_ms <= baseline.latency_ms
        and candidate.gpu_seconds <= baseline.gpu_seconds
        and candidate != baseline
    )


def next_experiment(experiment_id: str, hypothesis: str) -> Experiment:
    if not experiment_id.strip() or not hypothesis.strip():
        raise ValueError("experiment id and hypothesis are required")
    return Experiment(experiment_id=experiment_id, hypothesis=hypothesis)
