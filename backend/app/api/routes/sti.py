from pathlib import Path

from fastapi import APIRouter

from services.supreme.run_state import RunState
from services.supreme.run_store import RunStore

router = APIRouter(prefix="/sti", tags=["seldrune-sti"])


def _store() -> RunStore:
    path = Path("data") / "supreme-runs.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return RunStore(path)


@router.get("/telemetry")
def sti_telemetry() -> dict[str, object]:
    """Measured Seldrune STI execution telemetry for the Owner Console."""
    store = _store()
    counts = store.state_counts()
    recent = store.recent()
    forge = tuple(item for item in recent if item.run_id.startswith("forge:"))
    return {
        "system": "Seldrune STI — Aethelion Intelligence Foundry",
        "source": "durable-run-store",
        "counts": {state.value: counts[state] for state in RunState},
        "forge": {
            "queued": sum(item.state == RunState.QUEUED for item in forge),
            "running": sum(item.state == RunState.RUNNING for item in forge),
            "verified": sum(item.state == RunState.VERIFIED for item in forge),
            "failed": sum(item.state == RunState.FAILED for item in forge),
            "recent_count": len(forge),
        },
        "recent": [
            {
                "run_id": item.run_id,
                "task_id": item.task_id,
                "state": item.state.value,
                "attempts": item.attempts,
                "evidence_count": len(item.evidence),
                "error": item.error,
            }
            for item in recent
        ],
    }
