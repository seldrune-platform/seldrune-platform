from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvolutionArc:
    start: int
    end: int
    name: str
    focus: str
    gate: str
    evidence_status: str


_ARCS = (
    EvolutionArc(
        22,
        29,
        "Execution Truth",
        "Deterministic owner orders, governed execution, receipts, and fail-closed truth gates.",
        "Every external action is represented by a real ToolRun and provider receipt.",
        "implemented",
    ),
    EvolutionArc(
        30,
        39,
        "Action Fabric",
        "Provider bootstrap, tool defaults, preflight checks, approvals, and credential isolation.",
        "Configured providers are remotely verifiable without leaking credentials.",
        "implemented",
    ),
    EvolutionArc(
        40,
        49,
        "Live Intelligence",
        "Face v0.2 frame/stream execution, ONNX/CUDA runtime, WebRTC evidence, and media gates.",
        "Production claims remain locked behind retained runtime evidence.",
        "implemented",
    ),
    EvolutionArc(
        50,
        59,
        "Reality Compiler",
        (
            "Aetherion hypothesis compilation, bounded digital twins, "
            "simulation, and evidence receipts."
        ),
        "Simulation is clearly separated from measured real-world verification.",
        "implemented",
    ),
    EvolutionArc(
        60,
        69,
        "Self-Expansion",
        (
            "Capability discovery, sandbox construction, validation, "
            "skill promotion, and reusable playbooks."
        ),
        "New capabilities must pass verification before registration and reuse.",
        "registered",
    ),
    EvolutionArc(
        70,
        79,
        "Resilience Mesh",
        (
            "Recovery orchestration, degraded-dependency handling, "
            "backup/restore evidence, and incident response."
        ),
        "Recovery objectives and restore evidence must be measured in production.",
        "registered",
    ),
    EvolutionArc(
        80,
        89,
        "Elastic Compute",
        (
            "Cost-aware cloud/GPU scheduling, workload placement, "
            "capacity control, and runtime telemetry."
        ),
        "Elastic execution must preserve budgets, tenant isolation, and evidence lineage.",
        "registered",
    ),
    EvolutionArc(
        90,
        99,
        "Universal Organization",
        (
            "Recursive organization synthesis, domain factories, "
            "vendor/human routing, and parallel delivery."
        ),
        "Autonomy remains bounded by policy, budget, approvals, and evidence.",
        "registered",
    ),
    EvolutionArc(
        100,
        100,
        "Convergence",
        (
            "Unified owner intent, execution, verification, learning, "
            "deployment, and recovery control plane."
        ),
        "V100 is attained only when every prior arc is verified by production evidence.",
        "registered",
    ),
)


def evolution_registry() -> list[dict[str, Any]]:
    """Return every explicit V22–V100 technical contract without fabricated completion."""
    stages: list[dict[str, Any]] = []
    for arc in _ARCS:
        span = max(1, arc.end - arc.start)
        for version in range(arc.start, arc.end + 1):
            phase = (version - arc.start) / span if arc.end != arc.start else 1.0
            stages.append(
                {
                    "version": version,
                    "label": f"V{version}",
                    "arc": arc.name,
                    "focus": arc.focus,
                    "gate": arc.gate,
                    "contract_status": "registered",
                    "evidence_status": arc.evidence_status,
                    "arc_progress": round(phase, 3),
                }
            )
    return stages


def evolution_summary() -> dict[str, Any]:
    stages = evolution_registry()
    counts: dict[str, int] = {}
    for stage in stages:
        status = str(stage["evidence_status"])
        counts[status] = counts.get(status, 0) + 1
    verified = counts.get("verified", 0)
    implemented = counts.get("implemented", 0)
    registered = counts.get("registered", 0)
    return {
        "range": "V22–V100",
        "total_stages": len(stages),
        "first_version": stages[0]["version"],
        "last_version": stages[-1]["version"],
        "contract_coverage": len(stages) == 79,
        "evidence_counts": {
            "verified": verified,
            "implemented": implemented,
            "registered": registered,
        },
        "v100_attained": all(
            stage["evidence_status"] == "verified" for stage in stages
        ),
        "truth_boundary": (
            "All 79 version contracts exist. Registered or implemented stages are not "
            "reported as production-verified until retained evidence satisfies their gate."
        ),
    }


def evolution_payload() -> dict[str, Any]:
    return {
        "summary": evolution_summary(),
        "arcs": [
            {
                "start": arc.start,
                "end": arc.end,
                "name": arc.name,
                "focus": arc.focus,
                "gate": arc.gate,
                "evidence_status": arc.evidence_status,
            }
            for arc in _ARCS
        ],
        "stages": evolution_registry(),
    }
