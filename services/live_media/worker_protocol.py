"""Messages exchanged between the media gateway and GPU workers."""
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


@dataclass(frozen=True)
class InferenceResult:
    request_id: str
    timestamp_ms: int
    payload: bytes
    inference_ms: float
