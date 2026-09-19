"""Runtime evidence aggregation for the Aetherion research stack."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qnode_orchestrator import orchestrate
from .qnode_release_gate import evaluate


@dataclass(frozen=True)
class RuntimeEvidence:
    software_pipeline_verified: bool
    qnode_consensus_verified: bool
    physical_quantum_hardware_verified: bool
    quantum_speedup_verified: bool
    report_sha256: str
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def collect_runtime_evidence(program: QIRProgram) -> RuntimeEvidence:
    receipt = orchestrate(program)
    gate = evaluate(receipt)
    return RuntimeEvidence(
        software_pipeline_verified=gate.software_verified,
        qnode_consensus_verified=receipt.runtime.consensus.accepted,
        physical_quantum_hardware_verified=False,
        quantum_speedup_verified=False,
        report_sha256=receipt.report_sha256,
    )
