"""Deterministic research checkpoint receipts for Q-IR."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_fingerprint import program_fingerprint


@dataclass(frozen=True)
class CheckpointReceipt:
    program_sha256: str
    operation_count: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    persistent_hardware_state_verified: bool = False


def checkpoint(program: QIRProgram) -> CheckpointReceipt:
    return CheckpointReceipt(program_fingerprint(program), len(program.operations))
