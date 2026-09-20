"""Production-session orchestration for measured LiveShift evidence."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from time import monotonic

from .face_production_gate import FaceProductionEvidence
from .face_production_recorder import FaceProductionRecorder

RunSession = Callable[[FaceProductionRecorder], Awaitable[None]]


async def record_production_session(
    recorder: FaceProductionRecorder,
    run_session: RunSession,
    *,
    output_path: str | Path,
) -> FaceProductionEvidence:
    """Run one real media session and persist evidence only after clean completion.

    The same recorder is supplied to the runtime as its frame/audio/metadata
    observer. Exceptions and cancellations propagate without producing a
    production-evidence file.
    """
    target = Path(output_path)
    started = monotonic()
    try:
        await run_session(recorder)
    except BaseException:
        # A previous evidence file must never survive as proof for a failed run.
        target.unlink(missing_ok=True)
        raise

    duration = monotonic() - started
    try:
        return recorder.finish(
            session_duration_seconds=duration,
            output_path=target,
        )
    except BaseException:
        target.unlink(missing_ok=True)
        raise
