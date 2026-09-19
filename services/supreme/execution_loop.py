"""Single-job execution loop backed by the durable Seldrune run store."""

from collections.abc import Callable

from .run_state import RunRecord, failed, start, verified
from .run_store import RunStore
from .verifiers import CheckResult, all_checks_pass
from .worker_runtime import WorkResult


Executor = Callable[[RunRecord], WorkResult]
Verifier = Callable[[WorkResult], tuple[CheckResult, ...]]


def execute_once(
    store: RunStore,
    run_id: str,
    executor: Executor,
    verifier: Verifier | None = None,
) -> RunRecord:
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

    if not result.succeeded:
        broken = failed(running, result.error or "worker failed without diagnostic")
        store.save(broken)
        return broken

    if not result.evidence:
        broken = failed(running, "successful worker result has no evidence")
        store.save(broken)
        return broken

    if verifier is not None:
        try:
            checks = verifier(result)
            passed = all_checks_pass(checks)
        except (TypeError, ValueError) as exc:
            broken = failed(running, f"verification error: {exc}")
            store.save(broken)
            return broken
        if not passed:
            broken = failed(running, "proof mesh verification failed")
            store.save(broken)
            return broken
        evidence = tuple(check.evidence for check in checks)
    else:
        evidence = (result.evidence,)

    done = verified(running, evidence)
    store.save(done)
    return done
