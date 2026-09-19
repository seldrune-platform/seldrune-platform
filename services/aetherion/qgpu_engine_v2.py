"""Integrated Aetherion QGPU research engine v2."""

from __future__ import annotations

from dataclasses import dataclass

from .qef_runtime import QEFReceipt, execute_field
from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_fingerprint import program_fingerprint
from .qir_parallelism import ParallelismReceipt, estimate_parallelism


@dataclass(frozen=True)
class QGPUEngineReceipt:
    program_sha256: str
    field: QEFReceipt
    parallelism: ParallelismReceipt
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False
    quantum_speedup_verified: bool = False


def execute(program: QIRProgram) -> QGPUEngineReceipt:
    return QGPUEngineReceipt(
        program_fingerprint(program),
        execute_field(program),
        estimate_parallelism(program),
    )
