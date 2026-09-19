from services.supreme.run_state import RunRecord, RunState
from services.supreme.run_store import RunStore


def test_claim_queued_claims_parallel_batch_atomically(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    for index in range(12):
        store.save(RunRecord(f"run-{index:02d}", f"task-{index:02d}"))

    first = store.claim_queued(limit=8)
    second = store.claim_queued(limit=8)

    assert len(first) == 8
    assert len(second) == 4
    assert {item.run_id for item in first}.isdisjoint(
        {item.run_id for item in second}
    )
    assert all(item.state is RunState.RUNNING for item in first + second)
    assert all(item.attempts == 1 for item in first + second)


def test_claim_queued_rejects_invalid_parallelism(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    try:
        store.claim_queued(limit=0)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("expected ValueError")
