from services.supreme.parallel_worker import execute_claimed_batch
from services.supreme.run_state import RunRecord, RunState
from services.supreme.run_store import RunStore
from services.supreme.worker_runtime import WorkResult


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

    results = execute_claimed_batch(store, executor, max_parallel=4)
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

    results = execute_claimed_batch(store, executor, max_parallel=2)
    states = {item.task_id: item.state for item in results}
    assert states["good"] is RunState.VERIFIED
    assert states["bad"] is RunState.FAILED
