"""Release evidence gate for Aetherion QNode research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qnode_orchestrator import OrchestrationReceipt


@dataclass(frozen=True)
class ReleaseGate:
    software_verified: bool
    physical_quantum_verified: bool
    evidence: EvidenceLevel


def evaluate(receipt: OrchestrationReceipt) -> ReleaseGate:
    software_verified = receipt.runtime.fabric.all_completed and receipt.runtime.consensus.accepted
    return ReleaseGate(software_verified, False, EvidenceLevel.EXPERIMENTAL)
