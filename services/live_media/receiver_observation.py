"""Client-side observations for media returned over WebRTC."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class ReceivedVideoObservation:
    width: int
    height: int
    timestamp_ms: float | None


@dataclass(frozen=True)
class ReceivedAudioObservation:
    sample_rate_hz: int
    timestamp_ms: float | None


def _timestamp_ms(frame: object) -> float | None:
    pts = getattr(frame, "pts", None)
    time_base = getattr(frame, "time_base", None)
    if pts is None or time_base is None:
        return None
    return float(Fraction(pts) * Fraction(time_base) * 1000)


def observe_received_video(frame: object) -> ReceivedVideoObservation:
    width = int(frame.width)
    height = int(frame.height)
    if width <= 0 or height <= 0:
        raise ValueError("received video dimensions must be positive")
    return ReceivedVideoObservation(width, height, _timestamp_ms(frame))


def observe_received_audio(frame: object) -> ReceivedAudioObservation:
    sample_rate_hz = int(frame.sample_rate)
    if sample_rate_hz <= 0:
        raise ValueError("received audio sample rate must be positive")
    return ReceivedAudioObservation(sample_rate_hz, _timestamp_ms(frame))
