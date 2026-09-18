from services.live_media.failover import choose_with_failover
from services.live_media.gpu_scheduler import GPUWorker, WorkerState
from services.live_media.stream_health import StreamHealth
from services.live_media.worker_registry import WorkerRegistry


def test_registry_expires_stale_workers():
    registry = WorkerRegistry(stale_after_s=10)
    registry.heartbeat(GPUWorker("a", "in"), now=0)
    registry.heartbeat(GPUWorker("b", "sg"), now=9)
    assert registry.expire(now=11) == ["a"]
    assert [worker.worker_id for worker in registry.ready_workers(now=11)] == ["b"]


def test_registry_excludes_draining_worker():
    registry = WorkerRegistry()
    registry.heartbeat(
        GPUWorker("a", "in", state=WorkerState.DRAINING),
        now=0,
    )
    assert registry.ready_workers(now=1) == []


def test_failover_prefers_local_region():
    plan = choose_with_failover(
        [GPUWorker("sg-1", "sg"), GPUWorker("in-1", "in")],
        "in",
    )
    assert plan is not None
    assert plan.worker.worker_id == "in-1"
    assert not plan.cross_region


def test_stream_health():
    health = StreamHealth(80, 0.01, 30, 20, 15)
    assert health.healthy
    assert not StreamHealth(300, 0.01, 30, 20, 15).healthy
