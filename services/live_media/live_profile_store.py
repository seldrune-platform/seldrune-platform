"""Private mounted reference/profile store for LiveShell GPU adapters."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_FACE_NAMES = ("face.jpg", "face.jpeg", "face.png", "face.webp")
_VOICE_REFERENCE_SUFFIXES = {".wav", ".flac", ".ogg"}
_MAX_VOICE_REFERENCE_BYTES = 50 * 1024 * 1024


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
    untrusted = root / profile_id
    if untrusted.is_symlink():
        raise ValueError("profile directory cannot be a symlink")
    directory = untrusted.resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise ValueError("profile path escapes the configured root") from exc
    if not directory.is_dir():
        raise FileNotFoundError("authorized LiveShell profile media is not provisioned")
    return directory


def resolve_face_reference(profile_id: str) -> Path:
    directory = _profile_directory(profile_id)
    for name in _FACE_NAMES:
        candidate = directory / name
        if candidate.is_file() and not candidate.is_symlink():
            resolved = candidate.resolve()
            try:
                resolved.relative_to(directory)
            except ValueError as exc:
                raise ValueError("face reference path escapes its profile") from exc
            return resolved
    raise FileNotFoundError("authorized face reference image is not provisioned")


def resolve_voice_reference(profile_id: str) -> tuple[Path, str]:
    """Return an approved private voice reference and its verified SHA-256 digest."""
    directory = _profile_directory(profile_id)
    manifest_path = directory / "voice-reference.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise FileNotFoundError("authorized voice reference is not provisioned")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("voice reference manifest is unreadable") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"filename", "sha256"}:
        raise ValueError("voice reference manifest has an unsupported format")

    filename = manifest.get("filename")
    expected_hash = manifest.get("sha256")
    if (
        not isinstance(filename, str)
        or not filename
        or Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
        or Path(filename).suffix.lower() not in _VOICE_REFERENCE_SUFFIXES
        or not isinstance(expected_hash, str)
        or not _SHA256.fullmatch(expected_hash)
    ):
        raise ValueError("voice reference manifest entry is invalid")

    candidate = directory / filename
    if candidate.is_symlink() or not candidate.is_file():
        raise FileNotFoundError("voice reference audio is missing or unsafe")
    path = candidate.resolve()
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise ValueError("voice reference path escapes its profile") from exc

    size = path.stat().st_size
    if size <= 0 or size > _MAX_VOICE_REFERENCE_BYTES:
        raise ValueError("voice reference audio must be no larger than 50 MiB")

    digest = hashlib.sha256()
    with path.open("rb") as audio_file:
        for chunk in iter(lambda: audio_file.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_hash = digest.hexdigest()
    if not hmac.compare_digest(actual_hash, expected_hash.lower()):
        raise ValueError("voice reference digest does not match its manifest")
    return path, actual_hash


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
