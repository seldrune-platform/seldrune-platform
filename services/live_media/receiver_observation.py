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


class ReceiverObservationRecorder:
    """Accumulates observations made only after media reaches the WebRTC client."""

    def __init__(self) -> None:
        self.video_frames = 0
        self.latest_video: ReceivedVideoObservation | None = None
        self.latest_audio: ReceivedAudioObservation | None = None
        self._first_audio_timestamp_ms: float | None = None
        self._last_audio_timestamp_ms: float | None = None

    def record_video(self, frame: object) -> ReceivedVideoObservation:
        observation = observe_received_video(frame)
        self.video_frames += 1
        self.latest_video = observation
        return observation

    def record_audio(self, frame: object) -> ReceivedAudioObservation:
        observation = observe_received_audio(frame)
        self.latest_audio = observation
        if observation.timestamp_ms is not None:
            if self._first_audio_timestamp_ms is None:
                self._first_audio_timestamp_ms = observation.timestamp_ms
            if (
                self._last_audio_timestamp_ms is not None
                and observation.timestamp_ms <= self._last_audio_timestamp_ms
            ):
                raise ValueError("received audio timestamps must increase")
            self._last_audio_timestamp_ms = observation.timestamp_ms
        return observation

    @property
    def audio_duration_seconds(self) -> float:
        if (
            self._first_audio_timestamp_ms is None
            or self._last_audio_timestamp_ms is None
        ):
            return 0.0
        return (self._last_audio_timestamp_ms - self._first_audio_timestamp_ms) / 1000.0
