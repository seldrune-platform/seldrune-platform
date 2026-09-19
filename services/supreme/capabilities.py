"""Experimental capability registry for Seldrune SUPREME.

Names are research targets. A capability is never treated as achieved until its
benchmark gate is satisfied.
"""

from dataclasses import dataclass
from enum import StrEnum


class CapabilityState(StrEnum):
    CONCEPT = "concept"
    PROTOTYPE = "prototype"
    VERIFIED = "verified"


@dataclass(frozen=True)
class Capability:
    key: str
    purpose: str
    metric: str
    state: CapabilityState = CapabilityState.CONCEPT


ALIEN_CAPABILITIES = (
    Capability("time_fork", "Run competing future execution plans before commitment.", "verified_success_rate"),
    Capability("dream_lab", "Use idle compute for bounded hypothesis and experiment generation.", "useful_discoveries_per_gpu_hour"),
    Capability("skill_genesis", "Turn verified solutions into reusable executable skills.", "skill_reuse_success_rate"),
    Capability("unknown_radar", "Detect unsupported conclusions and launch evidence acquisition.", "uncertainty_calibration_error"),
    Capability("expert_civilization", "Spawn cooperating specialist populations around one objective.", "completed_work_per_wall_clock_hour"),
    Capability("evolution_arena", "Test candidate system improvements in isolated benchmark tournaments.", "validated_improvement_rate"),
    Capability("hyper_context", "Compress project state into retrievable working representations.", "retrieval_fidelity_per_byte"),
    Capability("counterfactual_worlds", "Simulate alternative decisions and compare measurable outcomes.", "prediction_calibration"),
    Capability("proof_mesh", "Require independent executable or evidence-based verification for critical claims.", "verified_error_escape_rate"),
    Capability("compute_shapeshift", "Continuously map work to the cheapest capable compute path.", "successful_tasks_per_gpu_second"),
)


def capability(key: str) -> Capability:
    for item in ALIEN_CAPABILITIES:
        if item.key == key:
            return item
    raise KeyError(key)
