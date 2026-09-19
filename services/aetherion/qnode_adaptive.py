"""Adaptive node planning for Aetherion software QNodes."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram


@dataclass(frozen=True)
class AdaptivePlan:
    operation_count: int
    worker_count: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def plan_workers(program: QIRProgram, maximum: int = 8) -> AdaptivePlan:
    if maximum < 1:
        raise ValueError("maximum must be positive")
    count = len(program.operations)
    return AdaptivePlan(count, min(maximum, max(1, count)))
