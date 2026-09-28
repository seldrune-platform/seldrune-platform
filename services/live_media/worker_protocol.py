"""Provider-neutral request and result contracts for cloud GPU workers."""

from dataclasses import dataclass
from enum import StrEnum


class MediaKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True)
class InferenceRequest:
    request_id: str
    session_id: str
    media_kind: MediaKind
    profile_id: str
    timestamp_ms: int
    payload: bytes
    sequence: int = 0
    width: int = 1280
    height: int = 720
    fps: float = 30.0
    sample_rate_hz: int = 48000
    channels: int = 1
    pixel_format: str | None = None


@dataclass(frozen=True)
class InferenceResult:
    request_id: str
    timestamp_ms: int
    payload: bytes
    inference_ms: float
    quality_evidence: dict[str, object] | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    pixel_format: str | None = None
