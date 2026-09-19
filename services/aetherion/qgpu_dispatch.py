"""Universal workload dispatcher for executable Aetherion research kernels."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_kernels import KernelKind, KernelReceipt, run_kernel
from .qgpu_model import EvidenceLevel, WorkloadDomain


@dataclass(frozen=True)
class DispatchReceipt:
    domain: WorkloadDomain
    kernel: KernelReceipt
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def dispatch_pair(
    domain: WorkloadDomain,
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> DispatchReceipt:
    mapping = {
        WorkloadDomain.AI: KernelKind.DOT_PRODUCT,
        WorkloadDomain.GRAPHICS: KernelKind.MEDIA_BLEND,
        WorkloadDomain.SIMULATION: KernelKind.SIMULATION_STEP,
        WorkloadDomain.MEDIA: KernelKind.MEDIA_BLEND,
        WorkloadDomain.SCIENTIFIC: KernelKind.DOT_PRODUCT,
        WorkloadDomain.GENERAL_PARALLEL: KernelKind.VECTOR_ADD,
    }
    return DispatchReceipt(domain, run_kernel(mapping[domain], left, right))
