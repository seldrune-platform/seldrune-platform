"""Tensor kernel primitives for Aetherion QGPU research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class TensorReceipt:
    output: tuple[tuple[float, ...], ...]
    multiply_accumulates: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_benchmark: bool = False


def matmul(
    left: tuple[tuple[float, ...], ...],
    right: tuple[tuple[float, ...], ...],
) -> TensorReceipt:
    if not left or not right or not right[0]:
        raise ValueError("matrices must be non-empty")
    width = len(left[0])
    if any(len(row) != width for row in left) or len(right) != width:
        raise ValueError("incompatible matrix shapes")
    columns = len(right[0])
    if any(len(row) != columns for row in right):
        raise ValueError("right matrix must be rectangular")
    output = tuple(
        tuple(sum(left[i][k] * right[k][j] for k in range(width)) for j in range(columns))
        for i in range(len(left))
    )
    return TensorReceipt(output, len(left) * columns * width)
