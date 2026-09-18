from dataclasses import dataclass
from enum import Enum


class WorkerState(str, Enum):
    READY = "ready"
    BUSY = "busy"
    DRAINING = "draining"


@dataclass
class GPUWorker:
    worker_id: str
    region: str
    state: WorkerState = WorkerState.READY
    active_sessions: int = 0
    capacity: int = 1

    @property
    def available(self) -> bool:
        return self.state == WorkerState.READY and self.active_sessions < self.capacity


def choose_worker(workers: list[GPUWorker], region: str) -> GPUWorker | None:
    eligible = [worker for worker in workers if worker.available]
    if not eligible:
        return None
    eligible.sort(key=lambda worker: (worker.region != region, worker.active_sessions))
    return eligible[0]
