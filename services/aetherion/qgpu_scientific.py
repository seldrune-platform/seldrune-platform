"""Scientific-compute stencil kernel for Aetherion research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class ScientificReceipt:
    output: tuple[float, ...]
    operations: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def diffusion_step(values: tuple[float, ...], alpha: float = 0.1) -> ScientificReceipt:
    if len(values) < 3:
        raise ValueError("diffusion stencil requires at least three values")
    output = list(values)
    for i in range(1, len(values) - 1):
        output[i] = values[i] + alpha * (values[i - 1] - 2 * values[i] + values[i + 1])
    return ScientificReceipt(tuple(output), (len(values) - 2) * 6)
