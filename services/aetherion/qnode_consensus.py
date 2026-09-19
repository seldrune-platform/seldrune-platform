"""Evidence consensus for reports produced by Aetherion QNodes."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qnode import QNodeReport


@dataclass(frozen=True)
class ConsensusReceipt:
    accepted: bool
    completed_nodes: int
    total_nodes: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def verify_consensus(reports: tuple[QNodeReport, ...]) -> ConsensusReceipt:
    completed = sum(report.completed for report in reports)
    return ConsensusReceipt(bool(reports) and completed == len(reports), completed, len(reports))
