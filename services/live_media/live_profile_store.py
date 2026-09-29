"""Private mounted reference/profile store for LiveShell GPU adapters."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
_FACE_NAMES = ("face.jpg", "face.jpeg", "face.png", "face.webp")


@dataclass(frozen=True)
class VoiceStyleProfile:
    """Low-latency, non-identity voice styling controls."""

    gain_db: float = 0.0
    presence: float = 0.0
    warmth: float = 0.0
    pitch_semitones: float = 0.0

    def validate(self) -> None:
        if not -6.0 <= self.gain_db <= 6.0:
            raise ValueError("voice style gain must be between -6 and 6 dB")
        if not -1.0 <= self.presence <= 1.0:
            raise ValueError("voice style presence must be between -1 and 1")
        if not -1.0 <= self.warmth <= 1.0:
            raise ValueError("voice style warmth must be between -1 and 1")
        if not -8.0 <= self.pitch_semitones <= 8.0:
            raise ValueError("voice style pitch must be between -8 and 8 semitones")


def profile_root() -> Path:
    return Path(
        os.getenv("SELDRUNE_LIVE_PROFILE_ROOT", "/workspace/seldrune-live-profiles")
    ).resolve()


def _profile_directory(profile_id: str) -> Path:
    if not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id):
        raise ValueError("invalid LiveShell profile id")
    root = profile_root()
    directory = (root / profile_id).resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise ValueError("profile path escapes the configured root") from exc
    if not directory.is_dir() or directory.is_symlink():
        raise FileNotFoundError("authorized LiveShell profile media is not provisioned")
    return directory


def resolve_face_reference(profile_id: str) -> Path:
    directory = _profile_directory(profile_id)
    for name in _FACE_NAMES:
        candidate = directory / name
        if candidate.is_file() and not candidate.is_symlink():
            resolved = candidate.resolve()
            resolved.relative_to(profile_root())
            return resolved
    raise FileNotFoundError("authorized face reference image is not provisioned")


def load_voice_style(profile_id: str) -> VoiceStyleProfile:
    directory = _profile_directory(profile_id)
    path = directory / "voice-style.json"
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("authorized voice style profile is not provisioned")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("voice style profile is unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError("voice style profile must be a JSON object")
    allowed = {"gain_db", "presence", "warmth", "pitch_semitones"}
    if set(value).difference(allowed):
        raise ValueError("voice style profile contains unsupported controls")
    try:
        profile = VoiceStyleProfile(
            gain_db=float(value.get("gain_db", 0.0)),
            presence=float(value.get("presence", 0.0)),
            warmth=float(value.get("warmth", 0.0)),
            pitch_semitones=float(value.get("pitch_semitones", 0.0)),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("voice style controls must be numeric") from exc
    profile.validate()
    return profile
