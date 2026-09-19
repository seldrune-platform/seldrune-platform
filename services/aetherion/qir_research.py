"""Unified research receipt for the current Aetherion Q-IR pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_reversible import ReversibleReceipt, analyze_reversibility
from .qir_verifier import VerificationReceipt, optimize_and_verify


@dataclass(frozen=True)
class QIRResearchReceipt:
    verification: VerificationReceipt
    reversibility: ReversibleReceipt
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False
    quantum_speedup_verified: bool = False


def run_qir_research(program: QIRProgram) -> QIRResearchReceipt:
    return QIRResearchReceipt(
        verification=optimize_and_verify(program),
        reversibility=analyze_reversibility(program),
    )
