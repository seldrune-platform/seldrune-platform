"""Measured quality contracts for realistic live face and voice transforms.

Evidence is produced by trusted model-side evaluators over decoded output.
This module checks the evidence; it does not infer quality from nonempty bytes
or claim that any particular model is realistic.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any


class RealismEvidenceError(ValueError):
    """A live transform is missing or fails its configured quality evidence."""


def _finite_number(value: object, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RealismEvidenceError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise RealismEvidenceError(f"{name} is outside the allowed range")
    return result


def _score(value: object, name: str) -> float:
    result = _finite_number(value, name)
    if not 0.0 <= result <= 1.0:
        raise RealismEvidenceError(f"{name} must be between 0 and 1")
    return result


def _evaluator(evaluator_id: str, evaluator_version: str) -> None:
    if (
        not isinstance(evaluator_id, str)
        or not evaluator_id.strip()
        or len(evaluator_id) > 128
    ):
        raise RealismEvidenceError("a named quality evaluator is required")
    if (
        not isinstance(evaluator_version, str)
        or not evaluator_version.strip()
        or len(evaluator_version) > 64
    ):
        raise RealismEvidenceError("a versioned quality evaluator is required")


@dataclass(frozen=True)
class FaceRealismEvidence:
    """Windowed face-transform measurements over the final decoded video."""

    evaluator_id: str
    evaluator_version: str
    window_frames: int
    output_width: int
    output_height: int
    output_fps: float
    identity_similarity: float
    temporal_consistency: float
    blend_quality: float
    p95_inference_ms: float

    def validate(self) -> None:
        _evaluator(self.evaluator_id, self.evaluator_version)
        if type(self.window_frames) is not int or self.window_frames < 2:
            raise RealismEvidenceError("face evidence needs a multi-frame window")
        if type(self.output_width) is not int or type(self.output_height) is not int:
            raise RealismEvidenceError("decoded face output dimensions are required")
        if self.output_width < 1 or self.output_height < 1:
            raise RealismEvidenceError("decoded face output dimensions must be positive")
        _finite_number(self.output_fps, "output_fps", minimum=0.001)
        _score(self.identity_similarity, "identity_similarity")
        _score(self.temporal_consistency, "temporal_consistency")
        _score(self.blend_quality, "blend_quality")
        _finite_number(self.p95_inference_ms, "p95_inference_ms", minimum=0.001)


@dataclass(frozen=True)
class VoiceRealismEvidence:
    """Windowed voice measurements over decoded 48 kHz output audio."""

    evaluator_id: str
    evaluator_version: str
    window_duration_seconds: float
    sample_rate_hz: int
    channels: int
    speaker_similarity: float
    content_preservation: float
    naturalness: float
    clipped_fraction: float
    dropout_fraction: float
    p95_processing_ms: float

    def validate(self) -> None:
        _evaluator(self.evaluator_id, self.evaluator_version)
        _finite_number(self.window_duration_seconds, "window_duration_seconds", minimum=0.001)
        if type(self.sample_rate_hz) is not int or self.sample_rate_hz < 1:
            raise RealismEvidenceError("decoded voice sample rate is required")
        if type(self.channels) is not int or self.channels < 1:
            raise RealismEvidenceError("decoded voice channel count is required")
        _score(self.speaker_similarity, "speaker_similarity")
        _score(self.content_preservation, "content_preservation")
        _score(self.naturalness, "naturalness")
        _score(self.clipped_fraction, "clipped_fraction")
        _score(self.dropout_fraction, "dropout_fraction")
        _finite_number(self.p95_processing_ms, "p95_processing_ms", minimum=0.001)


@dataclass(frozen=True)
class FaceTransformOutput:
    payload: bytes
    evidence: FaceRealismEvidence


@dataclass(frozen=True)
class VoiceTransformOutput:
    payload: bytes
    evidence: VoiceRealismEvidence


@dataclass(frozen=True)
class RealismQualityPolicy:
    """Deployment-calibrated pass thresholds. No perceptual score defaults."""

    face_min_identity_similarity: float
    face_min_temporal_consistency: float
    face_min_blend_quality: float
    voice_min_speaker_similarity: float
    voice_min_content_preservation: float
    voice_min_naturalness: float
    voice_max_clipped_fraction: float
    voice_max_dropout_fraction: float
    max_processing_p95_ms: float
    max_av_drift_ms: float
    min_face_window_frames: int = 30
    min_voice_window_seconds: float = 1.0
    min_video_width: int = 1280
    min_video_height: int = 720
    min_video_fps: float = 30.0
    min_audio_sample_rate_hz: int = 48000

    def __post_init__(self) -> None:
        score_limits = (
            "face_min_identity_similarity",
            "face_min_temporal_consistency",
            "face_min_blend_quality",
            "voice_min_speaker_similarity",
            "voice_min_content_preservation",
            "voice_min_naturalness",
            "voice_max_clipped_fraction",
            "voice_max_dropout_fraction",
        )
        for name in score_limits:
            _score(getattr(self, name), name)
        _finite_number(self.max_processing_p95_ms, "max_processing_p95_ms", minimum=0.001)
        _finite_number(self.max_av_drift_ms, "max_av_drift_ms", minimum=0.0)
        _finite_number(self.min_voice_window_seconds, "min_voice_window_seconds", minimum=0.001)
        _finite_number(self.min_video_fps, "min_video_fps", minimum=0.001)
        for name in (
            "min_face_window_frames",
            "min_video_width",
            "min_video_height",
            "min_audio_sample_rate_hz",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise RealismEvidenceError(f"{name} must be a positive integer")

    @classmethod
    def from_json(cls, value: str) -> RealismQualityPolicy:
        """Load explicit deployment thresholds without silently filling gaps."""
        try:
            config = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RealismEvidenceError("realism quality policy must be valid JSON") from exc
        if not isinstance(config, dict):
            raise RealismEvidenceError("realism quality policy must be a JSON object")
        required = {
            "face_min_identity_similarity",
            "face_min_temporal_consistency",
            "face_min_blend_quality",
            "voice_min_speaker_similarity",
            "voice_min_content_preservation",
            "voice_min_naturalness",
            "voice_max_clipped_fraction",
            "voice_max_dropout_fraction",
            "max_processing_p95_ms",
            "max_av_drift_ms",
        }
        missing = required.difference(config)
        unknown = set(config).difference(cls.__dataclass_fields__)
        if missing or unknown:
            raise RealismEvidenceError("realism quality policy has missing or unknown fields")
        return cls(**config)


def validate_face_realism(
    evidence: FaceRealismEvidence, policy: RealismQualityPolicy
) -> dict[str, Any]:
    evidence.validate()
    long_edge = max(evidence.output_width, evidence.output_height)
    short_edge = min(evidence.output_width, evidence.output_height)
    checks = (
        evidence.window_frames >= policy.min_face_window_frames,
        long_edge >= policy.min_video_width,
        short_edge >= policy.min_video_height,
        evidence.output_fps >= policy.min_video_fps,
        evidence.identity_similarity >= policy.face_min_identity_similarity,
        evidence.temporal_consistency >= policy.face_min_temporal_consistency,
        evidence.blend_quality >= policy.face_min_blend_quality,
        evidence.p95_inference_ms <= policy.max_processing_p95_ms,
    )
    if not all(checks):
        raise RealismEvidenceError("face output failed its configured HD realism thresholds")
    return {"media_kind": "video", **asdict(evidence)}


def validate_voice_realism(
    evidence: VoiceRealismEvidence, policy: RealismQualityPolicy
) -> dict[str, Any]:
    evidence.validate()
    checks = (
        evidence.window_duration_seconds >= policy.min_voice_window_seconds,
        evidence.sample_rate_hz >= policy.min_audio_sample_rate_hz,
        evidence.speaker_similarity >= policy.voice_min_speaker_similarity,
        evidence.content_preservation >= policy.voice_min_content_preservation,
        evidence.naturalness >= policy.voice_min_naturalness,
        evidence.clipped_fraction <= policy.voice_max_clipped_fraction,
        evidence.dropout_fraction <= policy.voice_max_dropout_fraction,
        evidence.p95_processing_ms <= policy.max_processing_p95_ms,
    )
    if not all(checks):
        raise RealismEvidenceError("voice output failed its configured HD realism thresholds")
    return {"media_kind": "audio", **asdict(evidence)}


def validate_av_drift(
    audio_timestamp_ms: int,
    video_timestamp_ms: int,
    policy: RealismQualityPolicy,
) -> dict[str, int | float]:
    """Reject a paired output sample when its measured track drift is too high."""
    if type(audio_timestamp_ms) is not int or type(video_timestamp_ms) is not int:
        raise RealismEvidenceError("integer audio and video timestamps are required")
    drift_ms = audio_timestamp_ms - video_timestamp_ms
    if abs(drift_ms) > policy.max_av_drift_ms:
        raise RealismEvidenceError("audio/video drift exceeded its configured limit")
    return {
        "audio_timestamp_ms": audio_timestamp_ms,
        "video_timestamp_ms": video_timestamp_ms,
        "drift_ms": drift_ms,
        "max_drift_ms": policy.max_av_drift_ms,
    }
