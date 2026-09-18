import asyncio

import pytest

from services.live_media.backpressure import LatestFrameQueue
from services.live_media.processors import MediaFrame
from services.live_media.reconnect import ReconnectPolicy
from services.live_media.stream_lifecycle import StreamLifecycle, StreamState


def test_stream_lifecycle():
    lifecycle = StreamLifecycle()
    lifecycle.start()
    lifecycle.activate()
    assert lifecycle.state == StreamState.ACTIVE
    lifecycle.stop()
    lifecycle.close()
    assert lifecycle.state == StreamState.CLOSED


def test_invalid_activation():
    with pytest.raises(RuntimeError):
        StreamLifecycle().activate()


def test_reconnect_backoff_is_bounded():
    policy = ReconnectPolicy()
    assert policy.delay_ms(0) == 250
    assert policy.delay_ms(10) == 4000


def test_latest_frame_queue_drops_stale_frame():
    async def scenario():
        queue = LatestFrameQueue(maxsize=1)
        await queue.put(MediaFrame(b"old", 1))
        await queue.put(MediaFrame(b"new", 2))
        frame = await queue.get()
        assert frame.payload == b"new"
        assert queue.dropped == 1

    asyncio.run(scenario())
