"""Multi-objective cost model for Aetherion Q-IR experiments."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class ExecutionCost:
    operations: int
    memory_moves: int
    synchronizations: int
    information_loss: int = 0

    @property
    def score(self) -> int:
        return (
            self.operations
            + self.memory_moves * 3
            + self.synchronizations * 2
            + self.information_loss * 4
        )


@dataclass(frozen=True)
class CostReceipt:
    baseline: ExecutionCost
    candidate: ExecutionCost
    improvement: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_benchmark: bool = False


def compare_costs(baseline: ExecutionCost, candidate: ExecutionCost) -> CostReceipt:
    return CostReceipt(baseline, candidate, baseline.score - candidate.score)
