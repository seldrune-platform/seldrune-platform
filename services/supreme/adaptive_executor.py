"""Parallel execution that automatically queues bounded evolution on proof failure."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .evolution_cycle import EvolutionCycle, evolve_failures
from .parallel_worker import ClaimExecutor
from .run_state import RunRecord, RunState
from .run_store import RunStore
from .skill_evolution import Skill
from .verifiers import CheckResult
from .worker_runtime import WorkResult, validate_result

MeasuredVerifier = Callable[[WorkResult], tuple[CheckResult, ...]]


@dataclass(frozen=True)
class AdaptiveResult:
    run: RunRecord
    evolution: EvolutionCycle | None


def _execute_claimed_adaptive(
    store: RunStore,
    record: RunRecord,
    skill: Skill,
    executor: ClaimExecutor,
    verifier: MeasuredVerifier,
    generation: int,
) -> AdaptiveResult:
    try:
        work = executor(record)
        validate_result(work)
    except Exception as exc:
        failed_record = RunRecord(
            record.run_id,
            record.task_id,
            RunState.FAILED,
            record.attempts,
            record.evidence,
            f"{type(exc).__name__}: {exc}",
        )
        store.save(failed_record)
        return AdaptiveResult(failed_record, None)

    if not work.succeeded:
        failed_record = RunRecord(
            record.run_id,
            record.task_id,
            RunState.FAILED,
            record.attempts,
            record.evidence,
            work.error or "worker failed",
        )
        store.save(failed_record)
        return AdaptiveResult(failed_record, None)

    checks = verifier(work)
    if checks and all(check.state.value == "pass" for check in checks):
        verified_record = RunRecord(
            record.run_id,
            record.task_id,
            RunState.VERIFIED,
            record.attempts,
            tuple(check.evidence for check in checks),
        )
        store.save(verified_record)
        return AdaptiveResult(verified_record, None)

    failed_record = RunRecord(
        record.run_id,
        record.task_id,
        RunState.FAILED,
        record.attempts,
        record.evidence,
        "proof mesh verification failed",
    )
    store.save(failed_record)
    evolution = evolve_failures(store, skill, checks, generation)
    return AdaptiveResult(failed_record, evolution)


def execute_adaptive_batch(
    store: RunStore,
    skill: Skill,
    executor: ClaimExecutor,
    verifier: MeasuredVerifier,
    generation: int,
    max_parallel: int = 8,
) -> tuple[AdaptiveResult, ...]:
    """Claim and execute independent adaptive runs concurrently."""
    claimed = store.claim_queued(limit=max_parallel)
    if not claimed:
        return ()
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = [
            pool.submit(
                _execute_claimed_adaptive,
                store,
                record,
                skill,
                executor,
                verifier,
                generation,
            )
            for record in claimed
        ]
        return tuple(future.result() for future in futures)
