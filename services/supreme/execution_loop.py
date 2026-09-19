"""Single-job execution loop backed by the durable Seldrune run store."""

from collections.abc import Callable

from .run_state import RunRecord, failed, start, verified
from .run_store import RunStore
from .worker_runtime import WorkResult


Executor = Callable[[RunRecord], WorkResult]


def execute_once(store: RunStore, run_id: str, executor: Executor) -> RunRecord:
    record = store.load(run_id)
    if record is None:
        raise KeyError(run_id)

    running = start(record)
    store.save(running)

    try:
        result = executor(running)
    except Exception as exc:
        broken = failed(running, f"{type(exc).__name__}: {exc}")
        store.save(broken)
        return broken

    if result.succeeded:
        if not result.evidence:
            broken = failed(running, "successful worker result has no evidence")
            store.save(broken)
            return broken
        done = verified(running, (result.evidence,))
        store.save(done)
        return done

    broken = failed(running, result.error or "worker failed without diagnostic")
    store.save(broken)
    return broken
