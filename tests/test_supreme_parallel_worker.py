from services.supreme.parallel_worker import execute_claimed_batch
from services.supreme.run_state import RunRecord, RunState
from services.supreme.run_store import RunStore
from services.supreme.verifiers import threshold_check
from services.supreme.worker_runtime import WorkResult


def passing_verifier(result):
    return (threshold_check("quality", 0.9, 0.8, f"proof://{result.task_id}"),)


def test_parallel_worker_executes_claimed_batch(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    for index in range(6):
        store.save(RunRecord(f"run-{index}", f"task-{index}"))

    def executor(record):
        return WorkResult(
            record.task_id,
            True,
            f"artifact://{record.task_id}",
            None,
        )

    results = execute_claimed_batch(store, executor, max_parallel=4, verifier=passing_verifier)
    assert len(results) == 4
    assert all(item.state is RunState.VERIFIED for item in results)
    assert len(execute_claimed_batch(store, executor, max_parallel=4)) == 2


def test_parallel_worker_isolates_failure(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-good", "good"))
    store.save(RunRecord("run-bad", "bad"))

    def executor(record):
        if record.task_id == "bad":
            raise RuntimeError("isolated failure")
        return WorkResult(record.task_id, True, "artifact://good", None)

    results = execute_claimed_batch(store, executor, max_parallel=2, verifier=passing_verifier)
    states = {item.task_id: item.state for item in results}
    assert states["good"] is RunState.VERIFIED
    assert states["bad"] is RunState.FAILED


def test_parallel_worker_rejects_unverified_success(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-unverified", "unverified"))

    def executor(record):
        return WorkResult(record.task_id, True, "artifact://raw", None)

    result = execute_claimed_batch(store, executor, max_parallel=1)[0]
    assert result.state is RunState.FAILED
    assert result.error == "measured verifier required"


def test_parallel_worker_rejects_failed_measurement(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    store.save(RunRecord("run-low-quality", "low-quality"))

    def executor(record):
        return WorkResult(record.task_id, True, "artifact://raw", None)

    def failing_verifier(result):
        return (
            threshold_check(
                "quality",
                0.4,
                0.8,
                f"proof://{result.task_id}",
            ),
        )

    result = execute_claimed_batch(
        store,
        executor,
        max_parallel=1,
        verifier=failing_verifier,
    )[0]
    assert result.state is RunState.FAILED
    assert result.error == "proof mesh verification failed"
