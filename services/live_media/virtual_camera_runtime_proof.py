"""Runtime evidence gate for a real desktop virtual-camera device."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from .virtual_camera import VirtualCameraBridge


@dataclass(frozen=True)
class VirtualCameraRuntimeReceipt:
    state: str
    virtual_camera_connected: bool
    frames_delivered: int


async def prove_virtual_camera_delivery(sink: object, frame: object) -> VirtualCameraRuntimeReceipt:
    bridge = VirtualCameraBridge(sink)  # type: ignore[arg-type]
    evidence = await bridge.deliver(frame)
    return VirtualCameraRuntimeReceipt(
        state="succeeded" if evidence.verified else "failed",
        virtual_camera_connected=evidence.verified,
        frames_delivered=evidence.frames_delivered,
    )


def receipt_dict(receipt: VirtualCameraRuntimeReceipt) -> dict[str, object]:
    return asdict(receipt)


def prove_virtual_camera_delivery_sync(sink: object, frame: object) -> VirtualCameraRuntimeReceipt:
    return asyncio.run(prove_virtual_camera_delivery(sink, frame))
