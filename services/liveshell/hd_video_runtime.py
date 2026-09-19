"""HD video runtime primitives for Seldrune LiveShell.

This layer upgrades the transport contract to HD-sized frames while keeping
model quality and device readiness evidence-gated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from services.live_media.interfaces import MediaFrame

HDTransform = Callable[[object, object], Awaitable[object]]
ReferenceProvider = Callable[[str], object]


class FrameShape(Protocol):
    shape: tuple[int, ...]


@dataclass
class LiveShellHDVideoProcessor:
    """Authorized, reference-conditioned HD frame processor."""

    transform: HDTransform
    reference_provider: ReferenceProvider
    min_width: int = 1280
    min_height: int = 720

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        if not profile_id:
            raise ValueError("authorized LiveShell face profile is required")

        payload = frame.payload
        shape = getattr(payload, "shape", None)
        if shape is None or len(shape) < 3:
            raise ValueError("HD video payload must expose an image shape")

        height = int(shape[-3])
        width = int(shape[-2])
        if width < self.min_width or height < self.min_height:
            raise ValueError(
                f"LiveShell HD requires at least {self.min_width}x{self.min_height}"
            )

        reference = self.reference_provider(profile_id)
        if reference is None:
            raise ValueError("enrolled LiveShell face reference is required")

        transformed = await self.transform(payload, reference)
        output_shape = getattr(transformed, "shape", None)
        if output_shape != shape:
            raise ValueError("HD transform must preserve the input frame shape")

        return MediaFrame(payload=transformed, timestamp_ms=frame.timestamp_ms)
