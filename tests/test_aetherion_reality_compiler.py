import pytest

from backend.app.api.routes.aetherion import reality_compiler_demo
from services.aetherion.qgpu_model import EvidenceLevel
from services.aetherion.reality_compiler import (
    CandidateDisposition,
    InventionCandidate,
    RealityObjective,
    compile_reality,
)


def _objective() -> RealityObjective:
    return RealityObjective(
        objective_id="objective-1",
        statement="Find a bounded prototype candidate.",
        constraints=("safe", "testable"),
        success_metrics=("measured-output",),
    )


def _candidate(candidate_id: str, *, risk: float = 0.2) -> InventionCandidate:
    return InventionCandidate(
        candidate_id=candidate_id,
        title=f"Candidate {candidate_id}",
        principle="A falsifiable software-ranked hypothesis.",
        addressed_constraints=("safe", "testable"),
        prototype_steps=("Build bounded test.", "Record measurements."),
        feasibility=0.7,
        impact=0.8,
        novelty=0.6,
        readiness=0.5,
        risk=risk,
    )


def test_compiler_selects_viable_candidate_with_stable_receipt():
    first = compile_reality(_objective(), (_candidate("alpha"), _candidate("beta", risk=0.4)))
    second = compile_reality(_objective(), (_candidate("alpha"), _candidate("beta", risk=0.4)))

    assert first.selected_candidate_id == "alpha"
    assert first.report_sha256 == second.report_sha256
    assert len(first.report_sha256) == 64
    assert first.evidence is EvidenceLevel.EXPERIMENTAL
    assert not first.physical_prototype_verified
    assert not first.real_world_outcome_verified


def test_compiler_rejects_missing_constraints_and_high_risk():
    candidate = InventionCandidate(
        candidate_id="unsafe",
        title="Unsafe candidate",
        principle="Intentionally incomplete test hypothesis.",
        addressed_constraints=("testable",),
        prototype_steps=("Do not build.",),
        feasibility=0.2,
        impact=1.0,
        novelty=1.0,
        readiness=0.1,
        risk=0.95,
    )
    receipt = compile_reality(_objective(), (candidate,))
    evaluation = receipt.evaluations[0]

    assert receipt.selected_candidate_id is None
    assert evaluation.disposition is CandidateDisposition.REJECTED
    assert "missing-constraint:safe" in evaluation.failure_modes
    assert "risk-above-threshold" in evaluation.failure_modes


def test_compiler_validates_normalized_candidate_values():
    with pytest.raises(ValueError, match="risk must be normalized"):
        compile_reality(_objective(), (_candidate("invalid", risk=1.1),))


def test_reality_compiler_demo_endpoint_keeps_physical_claims_unverified():
    payload = reality_compiler_demo()

    assert payload["status"] == "experimental"
    assert payload["selected_candidate_id"] == "thermal-lattice"
    assert not payload["physical_prototype_verified"]
    assert not payload["real_world_outcome_verified"]
