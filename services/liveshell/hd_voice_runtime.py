"""LiveShell 48 kHz authorized-reference voice runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from services.live_media.processors import MediaFrame

VoiceTransform = Callable[[object, object], Awaitable[object]]
ReferenceProvider = Callable[[str], object]


@dataclass
class LiveShellHDVoiceProcessor:
    transform: VoiceTransform
    reference_provider: ReferenceProvider
    sample_rate: int = 48000

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        if not profile_id:
            raise ValueError("authorized LiveShell voice profile is required")
        reference = self.reference_provider(profile_id)
        if reference is None:
            raise ValueError("enrolled LiveShell voice reference is required")
        transformed = await self.transform(frame.payload, reference)
        if transformed is None:
            raise ValueError("voice transform returned no audio")
        return MediaFrame(payload=transformed, timestamp_ms=frame.timestamp_ms)
