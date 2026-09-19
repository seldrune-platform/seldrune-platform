"""Batch research runner combining current Aetherion Q-IR evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_information import InformationReceipt, analyze_information_flow
from .qir_partition import PartitionReceipt, partition_dependency_layers
from .qir_research import QIRResearchReceipt, run_qir_research


@dataclass(frozen=True)
class QIRBatchReceipt:
    research: QIRResearchReceipt
    information: InformationReceipt
    partition: PartitionReceipt
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False


def run_qir_batch(program: QIRProgram) -> QIRBatchReceipt:
    return QIRBatchReceipt(
        run_qir_research(program),
        analyze_information_flow(program),
        partition_dependency_layers(program),
    )
