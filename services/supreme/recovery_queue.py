"""Persist Forge recovery experiments as durable parallel execution runs."""

from .recovery_orchestrator import RecoveryPlan
from .run_state import RunRecord
from .run_store import RunStore


def persist_recovery_plan(
    store: RunStore,
    plan: RecoveryPlan,
) -> tuple[RunRecord, ...]:
    records = tuple(
        RunRecord(
            run_id=f"forge:{job.experiment_id}",
            task_id=job.experiment_id,
        )
        for job in plan.jobs
    )
    for record in records:
        existing = store.load(record.run_id)
        if existing is None:
            store.save(record)
    return tuple(store.load(record.run_id) or record for record in records)
