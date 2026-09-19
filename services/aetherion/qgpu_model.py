"""Aetherion QGPU hypothetical architecture model.

This formalizes an invented universal quantum-cloud GPU target. It is a
research model, not evidence that physical quantum GPU hardware exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceLevel(StrEnum):
    HYPOTHETICAL = "hypothetical"
    EXPERIMENTAL = "experimental"
    VERIFIED = "verified"


class WorkloadDomain(StrEnum):
    AI = "ai"
    GRAPHICS = "graphics"
    SIMULATION = "simulation"
    MEDIA = "media"
    SCIENTIFIC = "scientific"
    GENERAL_PARALLEL = "general-parallel"


@dataclass(frozen=True)
class QGPUWorkload:
    domain: WorkloadDomain
    state_space: int
    dependency_edges: int
    reusable_fraction: float
    sparse_fraction: float

    def validate(self) -> None:
        if self.state_space < 1 or self.dependency_edges < 0:
            raise ValueError("invalid workload graph")
        if not 0 <= self.reusable_fraction <= 1:
            raise ValueError("reusable_fraction must be normalized")
        if not 0 <= self.sparse_fraction <= 1:
            raise ValueError("sparse_fraction must be normalized")


@dataclass(frozen=True)
class QuantumExecutionField:
    candidate_states: int
    reducible_states: int
    surviving_states: int
    evidence: EvidenceLevel = EvidenceLevel.HYPOTHETICAL


@dataclass(frozen=True)
class QGPUPlan:
    domain: WorkloadDomain
    qir_version: str
    execution_field: QuantumExecutionField
    engines: tuple[str, ...]
    evidence: EvidenceLevel = EvidenceLevel.HYPOTHETICAL
    physical_quantum_hardware_verified: bool = False


def construct_execution_field(workload: QGPUWorkload) -> QuantumExecutionField:
    workload.validate()
    reducible_fraction = min(
        1.0,
        (workload.reusable_fraction + workload.sparse_fraction) / 2,
    )
    reducible = int(workload.state_space * reducible_fraction)
    return QuantumExecutionField(
        candidate_states=workload.state_space,
        reducible_states=reducible,
        surviving_states=workload.state_space - reducible,
    )


def compile_qgpu_plan(workload: QGPUWorkload) -> QGPUPlan:
    field = construct_execution_field(workload)
    return QGPUPlan(
        domain=workload.domain,
        qir_version="qir-0.1-hypothesis",
        execution_field=field,
        engines=(
            "qef-state-reduction",
            "dependency-fabric",
            "probabilistic-scheduler",
            "universal-tensor-graphics-engine",
            "q-memory",
        ),
    )
