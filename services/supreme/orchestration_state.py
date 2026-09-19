"""Persistent orchestration state for Seldrune STI development jobs."""

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
    state: RunState
    attempts: int = 0
    evidence: tuple[str, ...] = ()
    error: str | None = None


def start_run(record: RunRecord) -> RunRecord:
    if record.state is not RunState.QUEUED:
        raise ValueError("only queued runs can start")
    return RunRecord(
        record.run_id,
        record.task_id,
        RunState.RUNNING,
        record.attempts + 1,
        record.evidence,
    )


def verify_run(record: RunRecord, evidence: tuple[str, ...]) -> RunRecord:
    if record.state is not RunState.RUNNING:
        raise ValueError("only running jobs can be verified")
    if not evidence:
        raise ValueError("verified runs require evidence")
    return RunRecord(
        record.run_id,
        record.task_id,
        RunState.VERIFIED,
        record.attempts,
        evidence,
    )


def fail_run(record: RunRecord, error: str) -> RunRecord:
    if record.state is not RunState.RUNNING:
        raise ValueError("only running jobs can fail")
    if not error.strip():
        raise ValueError("failed runs require an error")
    return RunRecord(
        record.run_id,
        record.task_id,
        RunState.FAILED,
        record.attempts,
        record.evidence,
        error,
    )
