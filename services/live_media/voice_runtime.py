"""Provider-neutral, consent-gated real-time voice conversion runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .processors import AudioProcessor, MediaFrame

VoiceTransform = Callable[[object, str], Awaitable[object]]


class AuthorizedVoiceProcessor(AudioProcessor):
    """Apply an enrolled voice profile while preserving frame timing.

    The concrete model is injected so the WebRTC/media layer stays independent
    from a particular voice-conversion vendor or model.
    """

    def __init__(self, transform: VoiceTransform) -> None:
        self._transform = transform

    async def process(self, frame: MediaFrame, profile_id: str) -> MediaFrame:
        if not profile_id:
            raise ValueError("authorized voice profile is required")
        output = await self._transform(frame.payload, profile_id)
        return MediaFrame(payload=output, timestamp_ms=frame.timestamp_ms)
