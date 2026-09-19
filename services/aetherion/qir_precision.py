"""Precision-policy research model for universal QGPU workloads."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class PrecisionPolicy:
    requested_bits: int
    minimum_bits: int
    selected_bits: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def select_precision(requested_bits: int, minimum_bits: int) -> PrecisionPolicy:
    allowed = (8, 16, 32, 64)
    if minimum_bits not in allowed or requested_bits not in allowed:
        raise ValueError("precision must be one of 8, 16, 32, 64")
    selected = max(minimum_bits, requested_bits)
    return PrecisionPolicy(requested_bits, minimum_bits, selected)
