"""Virtual-camera delivery contract for LiveShift.

OS-specific camera drivers stay outside the cloud inference core. This module
provides the frame-sink boundary used by desktop adapters (OBS, v4l2loopback,
or platform camera extensions) and records delivery evidence without claiming
that an OS camera device exists.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol


class VirtualCameraSink(Protocol):
    """Destination capable of accepting an RGB video frame."""

    async def send(self, frame: object) -> None: ...


@dataclass(frozen=True)
class VirtualCameraEvidence:
    frames_delivered: int
    sink_connected: bool

    @property
    def verified(self) -> bool:
        return self.sink_connected and self.frames_delivered > 0


class VirtualCameraBridge:
    """Forward transformed LiveShift frames to a client-side camera sink."""

    def __init__(self, sink: VirtualCameraSink) -> None:
        self._sink = sink
        self._frames_delivered = 0

    async def deliver(self, frame: object) -> VirtualCameraEvidence:
        await self._sink.send(frame)
        self._frames_delivered += 1
        return VirtualCameraEvidence(
            frames_delivered=self._frames_delivered,
            sink_connected=True,
        )

    def deliver_sync(self, frame: object) -> VirtualCameraEvidence:
        return asyncio.run(self.deliver(frame))
