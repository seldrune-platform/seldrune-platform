"""Integrated parallel-node execution path for Aetherion research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_fingerprint import program_fingerprint
from .qir_parallelism import estimate_parallelism
from .qir_pipeline_v2 import run_pipeline_v2
from .qnode import QNodeRole
from .qnode_consensus import ConsensusReceipt, verify_consensus
from .qnode_fabric import QNodeFabricReceipt, run_parallel


@dataclass(frozen=True)
class QNodeRuntimeReceipt:
    program_sha256: str
    fabric: QNodeFabricReceipt
    consensus: ConsensusReceipt
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_nodes_verified: bool = False


def execute(program: QIRProgram) -> QNodeRuntimeReceipt:
    tasks = {
        QNodeRole.COMPILER: lambda: len(program.operations),
        QNodeRole.STATE_REDUCTION: lambda: run_pipeline_v2(program).optimized_operations,
        QNodeRole.MEMORY: lambda: len(program_fingerprint(program)),
        QNodeRole.EXECUTION: lambda: run_pipeline_v2(program).optimized_output,
        QNodeRole.VERIFICATION: lambda: int(run_pipeline_v2(program).equivalent),
    }
    fabric = run_parallel(tasks)
    return QNodeRuntimeReceipt(
        program_fingerprint(program),
        fabric,
        verify_consensus(fabric.reports),
    )
