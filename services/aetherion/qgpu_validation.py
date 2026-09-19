"""Validation gate for Aetherion QGPU experimental receipts."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_engine_v2 import QGPUEngineReceipt
from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class ValidationReceipt:
    accepted: bool
    reason: str
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def validate(receipt: QGPUEngineReceipt) -> ValidationReceipt:
    if not receipt.field.equivalent:
        return ValidationReceipt(False, "optimized execution changed output")
    if receipt.physical_quantum_hardware_verified:
        return ValidationReceipt(False, "experimental engine cannot self-verify hardware")
    return ValidationReceipt(True, "experimental software equivalence verified")
