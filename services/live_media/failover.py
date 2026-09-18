"""Regional worker selection and failover policy."""
from dataclasses import dataclass

from .gpu_scheduler import GPUWorker, choose_worker


@dataclass(frozen=True)
class FailoverPlan:
    worker: GPUWorker
    cross_region: bool


def choose_with_failover(
    workers: list[GPUWorker], preferred_region: str
) -> FailoverPlan | None:
    local = [worker for worker in workers if worker.region == preferred_region]
    selected = choose_worker(local, preferred_region)
    if selected is not None:
        return FailoverPlan(selected, cross_region=False)

    selected = choose_worker(workers, preferred_region)
    if selected is None:
        return None
    return FailoverPlan(selected, cross_region=selected.region != preferred_region)
