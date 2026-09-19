"""Lifecycle records for Seldrune development work."""

from dataclasses import dataclass
from enum import StrEnum


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    task_id: str
    state: RunState = RunState.QUEUED
    attempts: int = 0
    evidence: tuple[str, ...] = ()


def start(record: RunRecord) -> RunRecord:
    if record.state is not RunState.QUEUED:
        raise ValueError("run must be queued")
    return RunRecord(
        record.run_id,
        record.task_id,
        RunState.RUNNING,
        record.attempts + 1,
        record.evidence,
    )


def verified(record: RunRecord, evidence: tuple[str, ...]) -> RunRecord:
    if record.state is not RunState.RUNNING:
        raise ValueError("run must be running")
    if not evidence:
        raise ValueError("evidence is required")
    return RunRecord(
        record.run_id,
        record.task_id,
        RunState.VERIFIED,
        record.attempts,
        evidence,
    )
