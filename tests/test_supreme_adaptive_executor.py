from services.supreme.adaptive_executor import execute_adaptive_batch
from services.supreme.run_state import RunRecord, RunState
from services.supreme.run_store import RunStore
from services.supreme.skill_evolution import Skill
from services.supreme.verifiers import threshold_check
from services.supreme.worker_runtime import WorkResult


def test_failed_proof_automatically_queues_evolution(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-face", "face-quality"))
    skill = Skill("face-quality", "LiveShift face quality")

    def executor(record):
        return WorkResult(record.task_id, True, "artifact://frame", None)

    def verifier(result):
        return (threshold_check("identity", 0.5, 0.85, "proof://identity"),)

    result = execute_adaptive_batch(store, skill, executor, verifier, 1)[0]

    assert result.run.state is RunState.FAILED
    assert result.evolution is not None
    assert len(result.evolution.runs) == 1
    queued = result.evolution.runs[0]
    assert queued.state is RunState.QUEUED
    assert queued.run_id == "forge:skill-face-quality-g1"


def test_passing_proof_does_not_create_evolution(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-good", "good"))
    skill = Skill("good", "Verified skill")

    def executor(record):
        return WorkResult(record.task_id, True, "artifact://good", None)

    def verifier(result):
        return (threshold_check("quality", 0.9, 0.8, "proof://quality"),)

    result = execute_adaptive_batch(store, skill, executor, verifier, 1)[0]

    assert result.run.state is RunState.VERIFIED
    assert result.evolution is None
