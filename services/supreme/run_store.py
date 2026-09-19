"""SQLite-backed durable run storage for Seldrune development jobs."""

import json
import sqlite3
from pathlib import Path

from .run_state import RunRecord, RunState


class RunStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS supreme_runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                evidence TEXT NOT NULL,
                error TEXT
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, record: RunRecord) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT INTO supreme_runs
                (run_id, task_id, state, attempts, evidence, error)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                task_id=excluded.task_id,
                state=excluded.state,
                attempts=excluded.attempts,
                evidence=excluded.evidence,
                error=excluded.error""",
                (
                    record.run_id,
                    record.task_id,
                    record.state.value,
                    record.attempts,
                    json.dumps(record.evidence),
                    record.error,
                ),
            )

    def claim_queued(self, limit: int = 8) -> tuple[RunRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                """SELECT run_id, task_id, attempts, evidence, error
                FROM supreme_runs WHERE state = ?
                ORDER BY run_id LIMIT ?""",
                (RunState.QUEUED.value, limit),
            ).fetchall()
            claimed = []
            for run_id, task_id, attempts, evidence, error in rows:
                record = RunRecord(
                    run_id,
                    task_id,
                    RunState.RUNNING,
                    attempts + 1,
                    tuple(json.loads(evidence)),
                    error,
                )
                db.execute(
                    """UPDATE supreme_runs
                    SET state = ?, attempts = ?
                    WHERE run_id = ? AND state = ?""",
                    (
                        RunState.RUNNING.value,
                        record.attempts,
                        run_id,
                        RunState.QUEUED.value,
                    ),
                )
                claimed.append(record)
            return tuple(claimed)

    def state_counts(self) -> dict[RunState, int]:
        """Return measured durable run counts for Owner Console telemetry."""
        counts = {state: 0 for state in RunState}
        with self._connect() as db:
            rows = db.execute(
                "SELECT state, COUNT(*) FROM supreme_runs GROUP BY state"
            ).fetchall()
        for state, count in rows:
            counts[RunState(state)] = int(count)
        return counts

    def recent(self, limit: int = 12) -> tuple[RunRecord, ...]:
        """Return recent durable runs without inventing runtime activity."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        with self._connect() as db:
            rows = db.execute(
                """SELECT run_id, task_id, state, attempts, evidence, error
                FROM supreme_runs ORDER BY rowid DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(
            RunRecord(
                run_id,
                task_id,
                RunState(state),
                attempts,
                tuple(json.loads(evidence)),
                error,
            )
            for run_id, task_id, state, attempts, evidence, error in rows
        )

    def load(self, run_id: str) -> RunRecord | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT task_id, state, attempts, evidence, error
                FROM supreme_runs WHERE run_id = ?""",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        task_id, state, attempts, evidence, error = row
        return RunRecord(
            run_id,
            task_id,
            RunState(state),
            attempts,
            tuple(json.loads(evidence)),
            error,
        )
