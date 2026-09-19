"""Universal executable kernels for Aetherion QGPU research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .qgpu_model import EvidenceLevel


class KernelKind(StrEnum):
    VECTOR_ADD = "vector_add"
    DOT_PRODUCT = "dot_product"
    MEDIA_BLEND = "media_blend"
    SIMULATION_STEP = "simulation_step"


@dataclass(frozen=True)
class KernelReceipt:
    kind: KernelKind
    output: tuple[float, ...]
    operations: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_benchmark: bool = False


def run_kernel(kind: KernelKind, left: tuple[float, ...], right: tuple[float, ...]) -> KernelReceipt:
    if len(left) != len(right):
        raise ValueError("kernel inputs must have equal length")
    if kind is KernelKind.VECTOR_ADD:
        output = tuple(a + b for a, b in zip(left, right, strict=True))
        operations = len(left)
    elif kind is KernelKind.DOT_PRODUCT:
        output = (sum(a * b for a, b in zip(left, right, strict=True)),)
        operations = len(left) * 2
    elif kind is KernelKind.MEDIA_BLEND:
        output = tuple((a + b) / 2 for a, b in zip(left, right, strict=True))
        operations = len(left) * 2
    else:
        output = tuple(a + 0.5 * b for a, b in zip(left, right, strict=True))
        operations = len(left) * 2
    return KernelReceipt(kind, output, operations)
