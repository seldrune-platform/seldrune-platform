"""Integrated experiment suite for Aetherion Q-IR development."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_checkpoint import CheckpointReceipt, checkpoint
from .qir_parallelism import ParallelismReceipt, estimate_parallelism
from .qir_pipeline_v2 import PipelineV2Receipt, run_pipeline_v2


@dataclass(frozen=True)
class ExperimentSuiteReceipt:
    pipeline: PipelineV2Receipt
    checkpoint: CheckpointReceipt
    parallelism: ParallelismReceipt
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_quantum_hardware_verified: bool = False
    quantum_speedup_verified: bool = False


def run_experiment_suite(program: QIRProgram) -> ExperimentSuiteReceipt:
    return ExperimentSuiteReceipt(
        run_pipeline_v2(program),
        checkpoint(program),
        estimate_parallelism(program),
    )
