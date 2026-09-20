"""Measured media metadata shared by concrete realtime transports.

The values in this module are observations reported by the transport after
media has actually been delivered.  They are deliberately separate from
MediaFrame so processors cannot accidentally invent production evidence.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DeliveredVideoMetadata:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("delivered video dimensions must be positive")


@dataclass(frozen=True)
class DeliveredAudioMetadata:
    sample_rate_hz: int

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise ValueError("delivered audio sample rate must be positive")


class MeasuredMediaTransport(Protocol):
    """Optional contract implemented by transports with measured output metadata."""

    def delivered_video_metadata(self) -> DeliveredVideoMetadata | None: ...

    def delivered_audio_metadata(self) -> DeliveredAudioMetadata | None: ...
