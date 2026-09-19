"""Health projection from Aetherion evidence without inflating claims."""

from __future__ import annotations

from dataclasses import dataclass

from .runtime_evidence import RuntimeEvidence


@dataclass(frozen=True)
class EvidenceHealth:
    software_ready: bool
    research_status: str
    physical_qgpu_status: str


def project_health(evidence: RuntimeEvidence) -> EvidenceHealth:
    return EvidenceHealth(
        software_ready=(
            evidence.software_pipeline_verified
            and evidence.qnode_consensus_verified
        ),
        research_status="experimental",
        physical_qgpu_status=(
            "verified"
            if evidence.physical_quantum_hardware_verified
            else "unverified"
        ),
    )
