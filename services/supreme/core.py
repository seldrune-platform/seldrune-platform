"""Seldrune SUPREME v0.1: capability and execution contracts.

The first milestone is an orchestration substrate, not a claim of AGI.
It routes objectives by dependency structure, parallelism and verification need.
"""

from dataclasses import dataclass
from enum import StrEnum


class CognitiveMode(StrEnum):
    FAST = "fast"
    DEEP = "deep"
    CREATIVE = "creative"
    RESEARCH = "research"
    VERIFY = "verify"


@dataclass(frozen=True)
class Objective:
    goal: str
    mode: CognitiveMode = CognitiveMode.FAST
    accuracy_critical: bool = False
    max_parallelism: int = 4


@dataclass(frozen=True)
class ExecutionPolicy:
    parallelism: int
    require_verification: bool
    speculative_execution: bool
    preserve_provenance: bool


def plan_execution(objective: Objective) -> ExecutionPolicy:
    if not objective.goal.strip():
        raise ValueError("objective goal is required")
    if objective.max_parallelism < 1:
        raise ValueError("max_parallelism must be at least 1")

    verification = objective.accuracy_critical or objective.mode in {
        CognitiveMode.DEEP,
        CognitiveMode.RESEARCH,
        CognitiveMode.VERIFY,
    }
    speculation = objective.mode in {
        CognitiveMode.FAST,
        CognitiveMode.CREATIVE,
        CognitiveMode.RESEARCH,
    }

    return ExecutionPolicy(
        parallelism=objective.max_parallelism,
        require_verification=verification,
        speculative_execution=speculation,
        preserve_provenance=objective.mode
        in {CognitiveMode.RESEARCH, CognitiveMode.VERIFY},
    )
