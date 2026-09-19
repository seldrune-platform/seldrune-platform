"""Parallel research-node abstraction for Aetherion QGPU."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .qgpu_model import EvidenceLevel


class QNodeRole(StrEnum):
    COMPILER = "compiler"
    STATE_REDUCTION = "state_reduction"
    MEMORY = "memory"
    EXECUTION = "execution"
    VERIFICATION = "verification"


@dataclass(frozen=True)
class QNodeReport:
    role: QNodeRole
    completed: bool
    metric: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
