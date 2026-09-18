"""Lease-based registry for warm GPU media workers."""
from dataclasses import dataclass
from time import monotonic

from .gpu_scheduler import GPUWorker, WorkerState


@dataclass
class WorkerLease:
    worker: GPUWorker
    last_seen: float


class WorkerRegistry:
    def __init__(self, stale_after_s: float = 30.0) -> None:
        self.stale_after_s = stale_after_s
        self._workers: dict[str, WorkerLease] = {}

    def heartbeat(self, worker: GPUWorker, now: float | None = None) -> None:
        self._workers[worker.worker_id] = WorkerLease(
            worker=worker,
            last_seen=monotonic() if now is None else now,
        )

    def ready_workers(self, now: float | None = None) -> list[GPUWorker]:
        current = monotonic() if now is None else now
        return [
            lease.worker
            for lease in self._workers.values()
            if current - lease.last_seen <= self.stale_after_s
            and lease.worker.state == WorkerState.READY
        ]

    def expire(self, now: float | None = None) -> list[str]:
        current = monotonic() if now is None else now
        expired = [
            worker_id
            for worker_id, lease in self._workers.items()
            if current - lease.last_seen > self.stale_after_s
        ]
        for worker_id in expired:
            del self._workers[worker_id]
        return expired
