import pytest

from services.supreme.run_state import (
    RunRecord,
    RunState,
    failed,
    retry,
    start,
    verified,
)


def test_run_moves_from_queue_to_verified():
    running = start(RunRecord("run-1", "face_train"))
    done = verified(running, ("artifact://benchmark",))
    assert running.state is RunState.RUNNING
    assert running.attempts == 1
    assert done.state is RunState.VERIFIED


def test_verified_run_requires_evidence():
    running = start(RunRecord("run-2", "sti_forge"))
    with pytest.raises(ValueError, match="evidence"):
        verified(running, ())


def test_failed_run_can_be_requeued():
    running = start(RunRecord("run-3", "face_frame"))
    broken = failed(running, "inference benchmark failed")
    queued = retry(broken)
    assert broken.state is RunState.FAILED
    assert broken.error == "inference benchmark failed"
    assert queued.state is RunState.QUEUED
    assert queued.attempts == 1
    assert queued.error is None


def test_retry_is_bounded():
    record = RunRecord("run-4", "sti_skill", RunState.FAILED, attempts=3)
    with pytest.raises(ValueError, match="maximum attempts"):
        retry(record, max_attempts=3)


def test_failure_requires_diagnostic_error():
    running = start(RunRecord("run-5", "sti_proof"))
    with pytest.raises(ValueError, match="error"):
        failed(running, "")
