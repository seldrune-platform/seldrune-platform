import asyncio

import pytest

from services.live_media.gpu_scheduler import GPUWorker
from services.live_media.latency import LatencyBudget
from services.live_media.worker_pool import WorkerPool
from services.live_media.worker_protocol import (
    InferenceRequest,
    InferenceResult,
    MediaKind,
)


def test_latency_budget_is_interactive():
    assert LatencyBudget().interactive


def test_worker_pool_dispatch():
    async def fake_call(worker, request):
        return InferenceResult(
            request.request_id,
            request.timestamp_ms,
            request.payload,
            12.0,
        )

    pool = WorkerPool([GPUWorker("in-1", "in")], fake_call)
    request = InferenceRequest(
        "r1", "s1", MediaKind.VIDEO, "profile", 10, b"frame"
    )
    result = asyncio.run(pool.infer(request, "in"))
    assert result.payload == b"frame"
    assert pool.workers[0].active_sessions == 0


def test_worker_pool_rejects_when_full():
    async def fake_call(worker, request):
        raise AssertionError("must not dispatch")

    worker = GPUWorker("in-1", "in", active_sessions=1, capacity=1)
    pool = WorkerPool([worker], fake_call)
    request = InferenceRequest(
        "r1", "s1", MediaKind.AUDIO, "profile", 10, b"audio"
    )
    with pytest.raises(RuntimeError):
        asyncio.run(pool.infer(request, "in"))
