from dataclasses import dataclass, field
from enum import StrEnum


class ClientKind(StrEnum):
    WEB = "web"
    ANDROID = "android"
    IOS = "ios"
    DESKTOP = "desktop"


@dataclass(frozen=True)
class MediaCapabilities:
    max_width: int = 1280
    max_height: int = 720
    max_fps: int = 30
    audio: bool = True
    video: bool = True


@dataclass(frozen=True)
class TransformRequest:
    session_id: str
    user_id: str
    client: ClientKind
    face_profile_id: str | None = None
    voice_profile_id: str | None = None
    consent_token: str | None = None
    capabilities: MediaCapabilities = field(default_factory=MediaCapabilities)


@dataclass(frozen=True)
class SessionPlan:
    face_enabled: bool
    voice_enabled: bool
    width: int
    height: int
    fps: int
    synthetic_media_indicator: bool = True
