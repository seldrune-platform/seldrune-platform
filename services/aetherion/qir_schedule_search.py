"""Deterministic schedule-search experiment for Aetherion Q-IR."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class ScheduleCandidate:
    name: str
    memory_moves: int
    synchronization_points: int
    operations: int


@dataclass(frozen=True)
class ScheduleSearchReceipt:
    selected: ScheduleCandidate
    candidates_evaluated: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    quantum_speedup_verified: bool = False


def search_schedule(
    candidates: tuple[ScheduleCandidate, ...],
) -> ScheduleSearchReceipt:
    if not candidates:
        raise ValueError("at least one schedule candidate is required")
    selected = min(
        candidates,
        key=lambda c: (
            c.memory_moves * 3 + c.synchronization_points * 2 + c.operations,
            c.name,
        ),
    )
    return ScheduleSearchReceipt(selected, len(candidates))
