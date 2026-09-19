from services.supreme.execution_loop import execute_once
from services.supreme.run_state import RunRecord, RunState
from services.supreme.run_store import RunStore
from services.supreme.worker_runtime import WorkResult


def test_execution_loop_persists_verified_result(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-1", "sti_verify"))

    def executor(record):
        return WorkResult(record.task_id, True, "artifact://proof", None)

    result = execute_once(store, "run-1", executor)
    assert result.state is RunState.VERIFIED
    assert store.load("run-1") == result


def test_execution_loop_records_worker_failure(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-2", "face_frame"))

    def executor(record):
        return WorkResult(record.task_id, False, "", "inference failed")

    result = execute_once(store, "run-2", executor)
    assert result.state is RunState.FAILED
    assert result.error == "inference failed"


def test_execution_loop_records_exception(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-3", "sti_forge"))

    def executor(record):
        raise RuntimeError("worker unavailable")

    result = execute_once(store, "run-3", executor)
    assert result.state is RunState.FAILED
    assert "worker unavailable" in (result.error or "")


def test_success_without_evidence_is_failure(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-4", "sti_skill"))

    def executor(record):
        return WorkResult(record.task_id, True, "", None)

    result = execute_once(store, "run-4", executor)
    assert result.state is RunState.FAILED
    assert "no evidence" in (result.error or "")
