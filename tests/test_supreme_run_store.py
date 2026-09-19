from services.supreme.run_state import RunRecord, RunState, failed, start
from services.supreme.run_store import RunStore


def test_store_survives_new_store_instance(tmp_path):
    path = tmp_path / "supreme.db"
    first = RunStore(path)
    running = start(RunRecord("run-1", "face_train"))
    first.save(running)

    recovered = RunStore(path).load("run-1")
    assert recovered == running
    assert recovered.state is RunState.RUNNING


def test_store_updates_failure_diagnostics(tmp_path):
    path = tmp_path / "supreme.db"
    store = RunStore(path)
    running = start(RunRecord("run-2", "sti_forge"))
    store.save(running)
    broken = failed(running, "benchmark failed")
    store.save(broken)

    recovered = RunStore(path).load("run-2")
    assert recovered == broken
    assert recovered.error == "benchmark failed"


def test_unknown_run_returns_none(tmp_path):
    store = RunStore(tmp_path / "supreme.db")
    assert store.load("missing") is None
