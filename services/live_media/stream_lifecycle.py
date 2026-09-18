"""Lifecycle and cancellation primitives for real-time media sessions."""
import asyncio
from dataclasses import dataclass
from enum import StrEnum


class StreamState(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass
class StreamLifecycle:
    state: StreamState = StreamState.CREATED
    error: str | None = None

    def start(self) -> None:
        if self.state != StreamState.CREATED:
            raise RuntimeError("stream cannot start")
        self.state = StreamState.STARTING

    def activate(self) -> None:
        if self.state != StreamState.STARTING:
            raise RuntimeError("stream cannot activate")
        self.state = StreamState.ACTIVE

    def stop(self) -> None:
        if self.state in {StreamState.CLOSED, StreamState.FAILED}:
            return
        self.state = StreamState.STOPPING

    def close(self) -> None:
        self.state = StreamState.CLOSED

    def fail(self, error: Exception) -> None:
        self.error = type(error).__name__
        self.state = StreamState.FAILED


async def cancel_tasks(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
