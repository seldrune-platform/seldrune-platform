from services.supreme.evolution_cycle import evolve_failures
from services.supreme.run_state import RunState
from services.supreme.run_store import RunStore
from services.supreme.skill_evolution import Skill
from services.supreme.traceback_intelligence import trace_lineage
from services.supreme.verifiers import threshold_check


def test_evolution_cycle_creates_traceable_durable_recovery(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    skill = Skill("face-quality", "LiveShift face quality")
    checks = (
        threshold_check("identity", 0.5, 0.85, "proof://identity"),
        threshold_check("latency", 120, 200, "proof://latency", lower_is_better=True),
    )

    cycle = evolve_failures(store, skill, checks, 2)

    assert len(cycle.plan.objectives) == 1
    assert len(cycle.runs) == 1
    assert cycle.runs[0].state is RunState.QUEUED
    forge_node = cycle.trace[-1]
    lineage = trace_lineage(cycle.trace, forge_node.node_id)
    assert len(lineage) == 3
    assert lineage[-1].task_id == "face-quality"


def test_evolution_cycle_with_all_checks_passing_creates_no_jobs(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    skill = Skill("stable", "Stable capability")
    checks = (threshold_check("quality", 0.9, 0.8, "proof://quality"),)

    cycle = evolve_failures(store, skill, checks, 1)

    assert cycle.plan.jobs == ()
    assert cycle.runs == ()
    assert len(cycle.trace) == 1
