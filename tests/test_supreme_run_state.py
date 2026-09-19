import pytest

from services.supreme.run_state import RunRecord, RunState, start, verified


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
