"""Unified bounded evolution cycle for failed measured capabilities."""

from dataclasses import dataclass

from .recovery_orchestrator import RecoveryPlan, plan_recovery
from .recovery_queue import persist_recovery_plan
from .run_state import RunRecord
from .run_store import RunStore
from .skill_evolution import Skill
from .traceback_intelligence import TraceNode, validate_trace
from .verifiers import CheckResult


@dataclass(frozen=True)
class EvolutionCycle:
    plan: RecoveryPlan
    runs: tuple[RunRecord, ...]
    trace: tuple[TraceNode, ...]


def evolve_failures(
    store: RunStore,
    skill: Skill,
    checks: tuple[CheckResult, ...],
    generation: int,
) -> EvolutionCycle:
    plan = plan_recovery(skill, checks, generation)
    runs = persist_recovery_plan(store, plan)

    root_id = f"skill:{skill.skill_id}:g{generation}"
    trace: list[TraceNode] = [
        TraceNode(root_id, skill.skill_id, None, (), 1.0)
    ]
    for index, (objective, run) in enumerate(zip(plan.objectives, runs, strict=True)):
        gap_id = f"{root_id}:gap:{index}"
        trace.append(
            TraceNode(
                gap_id,
                objective.skill_id,
                root_id,
                (objective.gap,),
                1.0,
            )
        )
        trace.append(
            TraceNode(
                f"{gap_id}:forge",
                run.task_id,
                gap_id,
                (run.run_id,),
                1.0,
            )
        )

    result = tuple(trace)
    validate_trace(result)
    return EvolutionCycle(plan, runs, result)
