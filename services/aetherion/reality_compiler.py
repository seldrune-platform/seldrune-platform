"""Truth-gated candidate compiler for Aetherion Reality Compiler research.

This module ranks explicit design hypotheses under declared constraints. It is
an executable software experiment, not evidence that a proposed invention
works in the physical world.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from .qgpu_model import EvidenceLevel


class CandidateDisposition(StrEnum):
    VIABLE = "viable"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RealityObjective:
    objective_id: str
    statement: str
    constraints: tuple[str, ...]
    success_metrics: tuple[str, ...]

    def validate(self) -> None:
        if not self.objective_id.strip() or not self.statement.strip():
            raise ValueError("objective_id and statement are required")
        if not self.constraints:
            raise ValueError("at least one constraint is required")
        if not self.success_metrics:
            raise ValueError("at least one success metric is required")
        if len(set(self.constraints)) != len(self.constraints):
            raise ValueError("objective constraints must be unique")


@dataclass(frozen=True)
class InventionCandidate:
    candidate_id: str
    title: str
    principle: str
    addressed_constraints: tuple[str, ...]
    prototype_steps: tuple[str, ...]
    feasibility: float
    impact: float
    novelty: float
    readiness: float
    risk: float

    def validate(self) -> None:
        if not self.candidate_id.strip() or not self.title.strip() or not self.principle.strip():
            raise ValueError("candidate identity, title, and principle are required")
        if not self.prototype_steps:
            raise ValueError("candidate requires at least one prototype step")
        for field_name in ("feasibility", "impact", "novelty", "readiness", "risk"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be normalized")


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    disposition: CandidateDisposition
    constraint_coverage: float
    utility_score: float
    failure_modes: tuple[str, ...]
    simulated: bool = True
    physically_verified: bool = False


@dataclass(frozen=True)
class RealityCompileReceipt:
    objective_id: str
    selected_candidate_id: str | None
    explored_candidates: int
    rejected_candidates: int
    evaluations: tuple[CandidateEvaluation, ...]
    prototype_steps: tuple[str, ...]
    report_sha256: str
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_prototype_verified: bool = False
    real_world_outcome_verified: bool = False


def _evaluate(
    objective: RealityObjective,
    candidate: InventionCandidate,
) -> CandidateEvaluation:
    candidate.validate()
    known_constraints = set(objective.constraints)
    addressed = known_constraints.intersection(candidate.addressed_constraints)
    coverage = len(addressed) / len(known_constraints)
    failures = tuple(
        f"missing-constraint:{item}"
        for item in objective.constraints
        if item not in addressed
    )
    if candidate.feasibility < 0.35:
        failures += ("feasibility-below-threshold",)
    if candidate.risk > 0.80:
        failures += ("risk-above-threshold",)

    raw_score = (
        0.30 * candidate.impact
        + 0.25 * candidate.feasibility
        + 0.20 * coverage
        + 0.15 * candidate.readiness
        + 0.10 * candidate.novelty
        - 0.20 * candidate.risk
    )
    return CandidateEvaluation(
        candidate_id=candidate.candidate_id,
        disposition=(
            CandidateDisposition.REJECTED if failures else CandidateDisposition.VIABLE
        ),
        constraint_coverage=round(coverage, 6),
        utility_score=round(max(0.0, min(1.0, raw_score)), 6),
        failure_modes=failures,
    )


def _receipt_digest(
    objective: RealityObjective,
    evaluations: tuple[CandidateEvaluation, ...],
    selected_candidate_id: str | None,
    prototype_steps: tuple[str, ...],
) -> str:
    payload = {
        "objective": {
            "id": objective.objective_id,
            "statement": objective.statement,
            "constraints": list(objective.constraints),
            "success_metrics": list(objective.success_metrics),
        },
        "evaluations": [
            {
                "candidate_id": item.candidate_id,
                "disposition": item.disposition.value,
                "constraint_coverage": item.constraint_coverage,
                "utility_score": item.utility_score,
                "failure_modes": list(item.failure_modes),
                "simulated": item.simulated,
                "physically_verified": item.physically_verified,
            }
            for item in evaluations
        ],
        "selected_candidate_id": selected_candidate_id,
        "prototype_steps": list(prototype_steps),
        "physical_prototype_verified": False,
        "real_world_outcome_verified": False,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def compile_reality(
    objective: RealityObjective,
    candidates: tuple[InventionCandidate, ...],
    *,
    max_candidates: int = 64,
) -> RealityCompileReceipt:
    """Evaluate design hypotheses and emit an immutable experimental receipt."""
    objective.validate()
    if not candidates:
        raise ValueError("at least one candidate is required")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")

    bounded = candidates[:max_candidates]
    candidate_ids = tuple(item.candidate_id for item in bounded)
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate ids must be unique")

    evaluations = tuple(_evaluate(objective, item) for item in bounded)
    viable = tuple(
        item for item in evaluations if item.disposition is CandidateDisposition.VIABLE
    )
    selected = (
        sorted(viable, key=lambda item: (-item.utility_score, item.candidate_id))[0]
        if viable
        else None
    )
    by_id = {item.candidate_id: item for item in bounded}
    selected_id = selected.candidate_id if selected else None
    steps = by_id[selected_id].prototype_steps if selected_id else ()
    digest = _receipt_digest(objective, evaluations, selected_id, steps)
    return RealityCompileReceipt(
        objective_id=objective.objective_id,
        selected_candidate_id=selected_id,
        explored_candidates=len(evaluations),
        rejected_candidates=sum(
            item.disposition is CandidateDisposition.REJECTED for item in evaluations
        ),
        evaluations=evaluations,
        prototype_steps=steps,
        report_sha256=digest,
    )
