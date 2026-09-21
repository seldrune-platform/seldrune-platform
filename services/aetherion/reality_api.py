"""Framework-neutral payloads for the Aetherion Reality Compiler."""

from __future__ import annotations

from .reality_compiler import (
    InventionCandidate,
    RealityCompileReceipt,
    RealityObjective,
    compile_reality,
)


def _payload(receipt: RealityCompileReceipt) -> dict[str, object]:
    return {
        "compiler": "aetherion-reality-compiler-v0.1",
        "status": "experimental",
        "objective_id": receipt.objective_id,
        "selected_candidate_id": receipt.selected_candidate_id,
        "explored_candidates": receipt.explored_candidates,
        "rejected_candidates": receipt.rejected_candidates,
        "prototype_steps": list(receipt.prototype_steps),
        "report_sha256": receipt.report_sha256,
        "evidence": receipt.evidence.value,
        "physical_prototype_verified": receipt.physical_prototype_verified,
        "real_world_outcome_verified": receipt.real_world_outcome_verified,
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
            for item in receipt.evaluations
        ],
    }


def build_reality_payload(
    objective: RealityObjective,
    candidates: tuple[InventionCandidate, ...],
) -> dict[str, object]:
    return _payload(compile_reality(objective, candidates))


def build_demo_reality_payload() -> dict[str, object]:
    objective = RealityObjective(
        objective_id="demo-closed-loop-energy",
        statement="Explore a recoverable, lab-testable energy storage architecture.",
        constraints=(
            "recoverable-materials",
            "laboratory-testable",
            "continuous-discharge",
        ),
        success_metrics=("cycle-efficiency", "material-recovery", "safe-discharge"),
    )
    candidates = (
        InventionCandidate(
            candidate_id="thermal-lattice",
            title="Phase-change thermal lattice",
            principle="Store heat across modular phase-change cells and recover it electrically.",
            addressed_constraints=objective.constraints,
            prototype_steps=(
                "Model a single bounded thermal cell.",
                "Build a benchtop non-pressurized cell.",
                "Measure charge, discharge, loss, and material recovery.",
            ),
            feasibility=0.72,
            impact=0.68,
            novelty=0.48,
            readiness=0.62,
            risk=0.24,
        ),
        InventionCandidate(
            candidate_id="field-resonance",
            title="Field-resonance capsule hypothesis",
            principle="Hypothesize energy retention in a dynamically stabilized field.",
            addressed_constraints=("continuous-discharge",),
            prototype_steps=("Define a falsifiable field model.",),
            feasibility=0.12,
            impact=0.95,
            novelty=0.98,
            readiness=0.05,
            risk=0.91,
        ),
    )
    return build_reality_payload(objective, candidates)
