"""Second-generation executable Q-IR research pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram, execute
from .qir_constant_fold import fold_constants
from .qir_equivalence import reduce_common_subexpressions
from .qir_graph_metrics import GraphMetrics, graph_metrics
from .qir_integrity import IntegrityReceipt, validate_integrity
from .qir_pruning import prune_dead_states


@dataclass(frozen=True)
class PipelineV2Receipt:
    baseline_output: int
    optimized_output: int
    baseline_operations: int
    optimized_operations: int
    integrity: IntegrityReceipt
    graph: GraphMetrics
    equivalent: bool
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    hardware_benchmark: bool = False


def run_pipeline_v2(program: QIRProgram) -> PipelineV2Receipt:
    integrity = validate_integrity(program)
    if not integrity.valid:
        raise ValueError("invalid Q-IR program")
    baseline_output, baseline_ops = execute(program)
    optimized = fold_constants(program)
    optimized = reduce_common_subexpressions(optimized)
    optimized = prune_dead_states(optimized)
    optimized_output, optimized_ops = execute(optimized)
    return PipelineV2Receipt(
        baseline_output,
        optimized_output,
        baseline_ops,
        optimized_ops,
        integrity,
        graph_metrics(optimized),
        baseline_output == optimized_output,
    )
