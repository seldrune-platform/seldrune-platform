from dataclasses import dataclass
from enum import Enum


class ClientCommand(str, Enum):
    START = "start"
    STOP = "stop"
    SET_FACE = "set_face"
    SET_VOICE = "set_voice"
    SET_QUALITY = "set_quality"


@dataclass(frozen=True)
class ClientHello:
    device_id: str
    platform: str
    app_version: str
    region_hint: str | None = None


@dataclass(frozen=True)
class SessionCredentials:
    session_id: str
    access_token: str
    expires_in_seconds: int
    signaling_url: str
