"""Integrated universal Aetherion QGPU research runtime v3."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_dispatch import DispatchReceipt, dispatch_pair
from .qgpu_model import EvidenceLevel, WorkloadDomain
from .qgpu_state_space import StateSpaceReceipt, reduce_state_space
from .qmemory_v2 import QMemoryV2


@dataclass(frozen=True)
class RuntimeV3Receipt:
    dispatch: DispatchReceipt
    state_space: StateSpaceReceipt
    memory_capacity: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False
    quantum_speedup_verified: bool = False


def execute(
    domain: WorkloadDomain,
    left: tuple[float, ...],
    right: tuple[float, ...],
    memory: QMemoryV2 | None = None,
) -> RuntimeV3Receipt:
    active_memory = memory or QMemoryV2()
    state_space = reduce_state_space(
        len(left) + len(right),
        0,
        sum(value == 0 for value in left + right),
    )
    return RuntimeV3Receipt(
        dispatch_pair(domain, left, right),
        state_space,
        active_memory.capacity,
    )
