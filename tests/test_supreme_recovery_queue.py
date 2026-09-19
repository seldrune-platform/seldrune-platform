from services.supreme.recovery_orchestrator import plan_recovery
from services.supreme.recovery_queue import persist_recovery_plan
from services.supreme.run_state import RunState
from services.supreme.run_store import RunStore
from services.supreme.skill_evolution import Skill
from services.supreme.verifiers import threshold_check


def test_failed_measurements_become_durable_forge_runs(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    skill = Skill("face-quality", "LiveShift face quality")
    checks = (
        threshold_check("identity", 0.5, 0.85, "proof://identity"),
        threshold_check("quality", 0.6, 0.8, "proof://quality"),
    )
    plan = plan_recovery(skill, checks, 3)

    records = persist_recovery_plan(store, plan)

    assert [record.run_id for record in records] == [
        "forge:skill-face-quality-g3",
        "forge:skill-face-quality-g4",
    ]
    assert all(record.state is RunState.QUEUED for record in records)
    assert store.claim_queued(limit=8) != ()


def test_recovery_persistence_is_idempotent(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    skill = Skill("media", "Media quality")
    checks = (threshold_check("quality", 0.5, 0.8, "proof://quality"),)
    plan = plan_recovery(skill, checks, 1)

    first = persist_recovery_plan(store, plan)
    second = persist_recovery_plan(store, plan)

    assert first == second
