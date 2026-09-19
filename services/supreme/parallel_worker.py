"""Bounded parallel execution for atomically claimed Seldrune runs."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from .run_state import RunRecord, failed, verified
from .run_store import RunStore
from .worker_runtime import WorkResult, validate_result

ClaimExecutor = Callable[[RunRecord], WorkResult]


def _execute_claimed(
    store: RunStore,
    record: RunRecord,
    executor: ClaimExecutor,
) -> RunRecord:
    try:
        result = executor(record)
    except Exception as exc:
        final = failed(record, f"{type(exc).__name__}: {exc}")
        store.save(final)
        return final

    try:
        validate_result(result)
    except ValueError as exc:
        final = failed(record, str(exc))
    else:
        if result.succeeded:
            final = verified(record, (result.evidence,))
        else:
            final = failed(record, result.error or "worker failed")
    store.save(final)
    return final


def execute_claimed_batch(
    store: RunStore,
    executor: ClaimExecutor,
    max_parallel: int = 8,
) -> tuple[RunRecord, ...]:
    claimed = store.claim_queued(limit=max_parallel)
    if not claimed:
        return ()
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = [
            pool.submit(_execute_claimed, store, record, executor)
            for record in claimed
        ]
        return tuple(future.result() for future in futures)
