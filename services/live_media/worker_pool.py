"""Async dispatch layer for warm cloud inference workers."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .gpu_scheduler import GPUWorker, choose_worker
from .worker_protocol import InferenceRequest, InferenceResult

WorkerCall = Callable[[GPUWorker, InferenceRequest], Awaitable[InferenceResult]]


@dataclass
class WorkerPool:
    workers: list[GPUWorker]
    call_worker: WorkerCall

    async def infer(
        self, request: InferenceRequest, region: str
    ) -> InferenceResult:
        worker = choose_worker(self.workers, region)
        if worker is None:
            raise RuntimeError("no GPU worker capacity")
        worker.active_sessions += 1
        try:
            return await self.call_worker(worker, request)
        finally:
            worker.active_sessions -= 1
