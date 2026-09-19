"""Framework-neutral payload builder for Aetherion evidence endpoints."""

from __future__ import annotations

from .qir import QIRProgram
from .evidence_health import project_health
from .evidence_snapshot import evidence_snapshot
from .runtime_evidence import collect_runtime_evidence


def build_evidence_payload(program: QIRProgram) -> dict[str, object]:
    evidence = collect_runtime_evidence(program)
    health = project_health(evidence)
    return {
        "runtime": evidence_snapshot(program),
        "health": {
            "software_ready": health.software_ready,
            "research_status": health.research_status,
            "physical_qgpu_status": health.physical_qgpu_status,
        },
    }
