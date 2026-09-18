"""Bounded real-time queues that prefer freshness over stale media."""
import asyncio
from dataclasses import dataclass, field

from .processors import MediaFrame


@dataclass
class LatestFrameQueue:
    maxsize: int = 2
    dropped: int = 0
    _queue: asyncio.Queue[MediaFrame] = field(init=False)

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=self.maxsize)

    async def put(self, frame: MediaFrame) -> None:
        if self._queue.full():
            self._queue.get_nowait()
            self._queue.task_done()
            self.dropped += 1
        await self._queue.put(frame)

    async def get(self) -> MediaFrame:
        return await self._queue.get()
