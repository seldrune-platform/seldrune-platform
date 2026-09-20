"""Measured production-session evidence recording for Seldrune Face."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path

from services.live_media.face_production_gate import FaceProductionEvidence
from services.live_media.face_training_executor import sha256_file
from services.live_media.transport_metadata import (
    DeliveredAudioMetadata,
    DeliveredVideoMetadata,
)


class FaceProductionRecorder:
    """Collect returned-frame timing and atomically persist one session record."""

    def __init__(
        self,
        *,
        run_id: str,
        verification_receipt_path: str | Path,
        output_width: int,
        output_height: int,
        audio_sample_rate_hz: int | None,
        authorization_verified: bool,
        synthetic_media_indicator_verified: bool,
    ) -> None:
        self._run_id = run_id
        self._receipt_path = Path(verification_receipt_path)
        self._output_width = output_width
        self._output_height = output_height
        self._audio_sample_rate_hz = audio_sample_rate_hz
        self._authorization_verified = authorization_verified
        self._synthetic_media_indicator_verified = synthetic_media_indicator_verified
        self._latencies_ms: list[float] = []
        self._audio_duration_seconds = 0.0
        self._last_audio_timestamp_ms: int | None = None
        self._delivered_video_metadata: DeliveredVideoMetadata | None = None
        self._delivered_audio_metadata: DeliveredAudioMetadata | None = None

    def record_delivered_video_metadata(self, metadata: DeliveredVideoMetadata) -> None:
        self._delivered_video_metadata = metadata

    def record_delivered_audio_metadata(self, metadata: DeliveredAudioMetadata) -> None:
        self._delivered_audio_metadata = metadata

    def record_returned_frame(self, latency_ms: float) -> None:
        if not math.isfinite(latency_ms) or latency_ms <= 0:
            raise ValueError("returned-frame latency must be positive")
        self._latencies_ms.append(latency_ms)

    def record_audio_duration(self, duration_seconds: float) -> None:
        if self._audio_sample_rate_hz is None:
            raise ValueError("audio sample rate is required before recording audio")
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("audio duration must be positive")
        self._audio_duration_seconds += duration_seconds

    def record_returned_audio_timestamp(self, timestamp_ms: int) -> None:
        """Measure delivered audio duration from monotonic media timestamps."""
        if self._audio_sample_rate_hz is None:
            raise ValueError("audio sample rate is required before recording audio")
        if timestamp_ms < 0:
            raise ValueError("audio timestamp must be non-negative")
        previous = self._last_audio_timestamp_ms
        if previous is not None:
            delta_ms = timestamp_ms - previous
            if delta_ms <= 0:
                raise ValueError("audio timestamps must increase")
            self._audio_duration_seconds += delta_ms / 1000.0
        self._last_audio_timestamp_ms = timestamp_ms

    def finish(
        self,
        *,
        session_duration_seconds: float,
        output_path: str | Path,
    ) -> FaceProductionEvidence:
        if not self._receipt_path.is_file():
            raise ValueError("verification receipt file is required")
        if not self._latencies_ms:
            raise ValueError("production session returned no transformed frames")
        ordered = sorted(self._latencies_ms)
        percentile_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
        audio_duration = (
            self._audio_duration_seconds if self._audio_sample_rate_hz is not None else None
        )
        output_width = (
            self._delivered_video_metadata.width
            if self._delivered_video_metadata is not None
            else self._output_width
        )
        output_height = (
            self._delivered_video_metadata.height
            if self._delivered_video_metadata is not None
            else self._output_height
        )
        audio_sample_rate_hz = (
            self._delivered_audio_metadata.sample_rate_hz
            if self._delivered_audio_metadata is not None
            else self._audio_sample_rate_hz
        )
        evidence = FaceProductionEvidence(
            run_id=self._run_id,
            verification_receipt_sha256=sha256_file(self._receipt_path),
            frames_returned=len(ordered),
            session_duration_seconds=session_duration_seconds,
            p95_latency_ms=ordered[percentile_index],
            output_width=output_width,
            output_height=output_height,
            audio_sample_rate_hz=audio_sample_rate_hz,
            audio_duration_seconds=audio_duration,
            authorization_verified=self._authorization_verified,
            synthetic_media_indicator_verified=self._synthetic_media_indicator_verified,
        )
        evidence.validate()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(asdict(evidence), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
        return evidence
