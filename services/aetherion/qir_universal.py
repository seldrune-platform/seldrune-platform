"""Universal typed workload layer for Aetherion Q-IR research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .qgpu_model import EvidenceLevel, WorkloadDomain


class DataKind(StrEnum):
    SCALAR = "scalar"
    TENSOR = "tensor"
    PIXEL = "pixel"
    STATE = "state"


@dataclass(frozen=True)
class UniversalKernel:
    kernel_id: str
    domain: WorkloadDomain
    data_kind: DataKind
    elements: int
    dependencies: tuple[str, ...] = ()
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
