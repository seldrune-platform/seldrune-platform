"""Bounded parallel execution with mandatory measured verification."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from .run_state import RunRecord, failed, verified
from .run_store import RunStore
from .verifiers import CheckResult, all_checks_pass
from .worker_runtime import WorkResult, validate_result

ClaimExecutor = Callable[[RunRecord], WorkResult]
ClaimVerifier = Callable[[WorkResult], tuple[CheckResult, ...]]


def _execute_claimed(
    store: RunStore,
    record: RunRecord,
    executor: ClaimExecutor,
    verifier: ClaimVerifier | None,
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
        if not result.succeeded:
            final = failed(record, result.error or "worker failed")
        elif verifier is None:
            final = failed(record, "measured verifier required")
        else:
            try:
                checks = verifier(result)
                passed = all_checks_pass(checks)
            except (TypeError, ValueError) as exc:
                final = failed(record, f"verification error: {exc}")
            else:
                if passed:
                    final = verified(
                        record,
                        tuple(check.evidence for check in checks),
                    )
                else:
                    final = failed(record, "proof mesh verification failed")
    store.save(final)
    return final


def execute_claimed_batch(
    store: RunStore,
    executor: ClaimExecutor,
    max_parallel: int = 8,
    verifier: ClaimVerifier | None = None,
) -> tuple[RunRecord, ...]:
    claimed = store.claim_queued(limit=max_parallel)
    if not claimed:
        return ()
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = [
            pool.submit(_execute_claimed, store, record, executor, verifier)
            for record in claimed
        ]
        return tuple(future.result() for future in futures)
