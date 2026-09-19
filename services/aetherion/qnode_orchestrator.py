"""Higher-level orchestration receipt for parallel Aetherion software nodes."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qnode_adaptive import AdaptivePlan, plan_workers
from .qnode_determinism import report_digest
from .qnode_runtime import QNodeRuntimeReceipt, execute


@dataclass(frozen=True)
class OrchestrationReceipt:
    plan: AdaptivePlan
    runtime: QNodeRuntimeReceipt
    report_sha256: str
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    autonomous_background_execution: bool = False


def orchestrate(program: QIRProgram) -> OrchestrationReceipt:
    plan = plan_workers(program)
    runtime = execute(program)
    return OrchestrationReceipt(plan, runtime, report_digest(runtime.fabric.reports))
