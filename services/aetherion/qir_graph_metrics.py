"""Graph-complexity metrics for Aetherion Q-IR."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel
from .qir import QIRProgram
from .qir_partition import partition_dependency_layers


@dataclass(frozen=True)
class GraphMetrics:
    nodes: int
    edges: int
    depth: int
    maximum_width: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def graph_metrics(program: QIRProgram) -> GraphMetrics:
    layers = partition_dependency_layers(program).layers
    return GraphMetrics(
        nodes=len(program.operations),
        edges=sum(len(op.inputs) for op in program.operations),
        depth=len(layers),
        maximum_width=max((len(layer) for layer in layers), default=0),
    )
