"""Evidence-backed promotion gates for Seldrune Face production claims."""

from __future__ import annotations

import math
from dataclasses import dataclass
from string import hexdigits


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in hexdigits for character in value)


@dataclass(frozen=True)
class FaceProductionEvidence:
    """Measured delivery evidence; never inferred from implementation status."""

    run_id: str
    verification_receipt_sha256: str
    frames_returned: int
    session_duration_seconds: float
    p95_latency_ms: float
    output_width: int
    output_height: int
    audio_sample_rate_hz: int | None
    audio_duration_seconds: float | None
    authorization_verified: bool
    synthetic_media_indicator_verified: bool

    def validate(self) -> None:
        if not self.run_id.strip():
            raise ValueError("production run identity is required")
        if not _is_sha256(self.verification_receipt_sha256):
            raise ValueError("verification receipt SHA-256 is required")
        if self.frames_returned < 1:
            raise ValueError("production session must return transformed frames")
        if not math.isfinite(self.session_duration_seconds) or self.session_duration_seconds <= 0:
            raise ValueError("production session duration must be positive")
        if not math.isfinite(self.p95_latency_ms) or self.p95_latency_ms <= 0:
            raise ValueError("production p95 latency must be positive")
        if self.output_width < 1 or self.output_height < 1:
            raise ValueError("production output dimensions must be positive")
        audio_values = (self.audio_sample_rate_hz, self.audio_duration_seconds)
        if (audio_values[0] is None) != (audio_values[1] is None):
            raise ValueError("audio evidence must include sample rate and duration together")
        if self.audio_sample_rate_hz is not None and self.audio_sample_rate_hz < 1:
            raise ValueError("audio sample rate must be positive")
        if self.audio_duration_seconds is not None and (
            not math.isfinite(self.audio_duration_seconds) or self.audio_duration_seconds <= 0
        ):
            raise ValueError("audio duration must be positive")
        if not self.authorization_verified:
            raise ValueError("authorized identity verification is required")
        if not self.synthetic_media_indicator_verified:
            raise ValueError("synthetic-media indicator verification is required")


@dataclass(frozen=True)
class FaceProductionGates:
    live_session_verified: bool
    mobile_hd_output_verified: bool
    voice_hd_output_verified: bool


def evaluate_production_gates(evidence: FaceProductionEvidence) -> FaceProductionGates:
    """Promote only measured outputs that meet explicit product thresholds."""
    evidence.validate()
    live_session = (
        evidence.frames_returned >= 30
        and evidence.session_duration_seconds >= 1.0
        and evidence.p95_latency_ms <= 150.0
    )
    mobile_hd = live_session and evidence.output_width >= 1280 and evidence.output_height >= 720
    voice_hd = (
        live_session
        and evidence.audio_sample_rate_hz is not None
        and evidence.audio_sample_rate_hz >= 48_000
        and evidence.audio_duration_seconds is not None
        and evidence.audio_duration_seconds >= 1.0
    )
    return FaceProductionGates(live_session, mobile_hd, voice_hd)
