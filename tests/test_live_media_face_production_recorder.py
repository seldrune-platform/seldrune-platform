"""Tests for measured Face production-session evidence recording."""

import json

import pytest

from services.live_media.face_production_recorder import FaceProductionRecorder
from services.live_media.face_training_executor import sha256_file
from services.live_media.transport_metadata import (
    DeliveredAudioMetadata,
    DeliveredVideoMetadata,
)


def _recorder(tmp_path, **overrides) -> FaceProductionRecorder:
    receipt = tmp_path / "face-verification.json"
    receipt.write_bytes(b"verified-receipt")
    values = {
        "run_id": "live-session-001",
        "verification_receipt_path": receipt,
        "output_width": 1920,
        "output_height": 1080,
        "audio_sample_rate_hz": 48_000,
        "authorization_verified": True,
        "synthetic_media_indicator_verified": True,
    }
    values.update(overrides)
    return FaceProductionRecorder(**values)


def test_recorder_measures_p95_and_atomically_writes_evidence(tmp_path) -> None:
    recorder = _recorder(tmp_path)
    for latency in range(1, 101):
        recorder.record_returned_frame(float(latency))
    recorder.record_audio_duration(10.0)
    output = tmp_path / "evidence" / "face-production.json"

    evidence = recorder.finish(session_duration_seconds=10.0, output_path=output)

    assert evidence.frames_returned == 100
    assert evidence.p95_latency_ms == 95.0
    assert evidence.verification_receipt_sha256 == sha256_file(
        tmp_path / "face-verification.json"
    )
    assert json.loads(output.read_text(encoding="utf-8"))["p95_latency_ms"] == 95.0
    assert not output.with_suffix(".json.tmp").exists()


def test_recorder_refuses_empty_or_untrusted_session_evidence(tmp_path) -> None:
    output = tmp_path / "face-production.json"
    with pytest.raises(ValueError, match="no transformed frames"):
        _recorder(tmp_path).finish(session_duration_seconds=1.0, output_path=output)
    assert not output.exists()

    recorder = _recorder(tmp_path, authorization_verified=False)
    recorder.record_returned_frame(10.0)
    recorder.record_audio_duration(1.0)
    with pytest.raises(ValueError, match="authorized identity"):
        recorder.finish(session_duration_seconds=1.0, output_path=output)
    assert not output.exists()


def test_recorder_requires_audio_format_before_audio_measurement(tmp_path) -> None:
    recorder = _recorder(tmp_path, audio_sample_rate_hz=None)
    with pytest.raises(ValueError, match="sample rate"):
        recorder.record_audio_duration(1.0)


def test_recorder_derives_audio_duration_from_returned_timestamps(tmp_path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("verified", encoding="utf-8")
    recorder = FaceProductionRecorder(
        run_id="audio-session",
        verification_receipt_path=receipt,
        output_width=1280,
        output_height=720,
        audio_sample_rate_hz=48_000,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )
    recorder.record_returned_frame(10.0)
    recorder.record_returned_audio_timestamp(1_000)
    recorder.record_returned_audio_timestamp(1_500)
    recorder.record_returned_audio_timestamp(2_000)
    evidence = recorder.finish(
        session_duration_seconds=1.0,
        output_path=tmp_path / "production.json",
    )
    assert evidence.audio_duration_seconds == pytest.approx(1.0)


def test_recorder_rejects_non_monotonic_audio_timestamps(tmp_path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("verified", encoding="utf-8")
    recorder = FaceProductionRecorder(
        run_id="audio-session",
        verification_receipt_path=receipt,
        output_width=1280,
        output_height=720,
        audio_sample_rate_hz=48_000,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )
    recorder.record_returned_audio_timestamp(1_000)
    with pytest.raises(ValueError, match="timestamps must increase"):
        recorder.record_returned_audio_timestamp(1_000)


def test_recorder_prefers_measured_transport_metadata_over_configuration(tmp_path) -> None:
    recorder = _recorder(
        tmp_path,
        output_width=3840,
        output_height=2160,
        audio_sample_rate_hz=96_000,
    )
    recorder.record_delivered_video_metadata(DeliveredVideoMetadata(640, 360))
    recorder.record_delivered_audio_metadata(DeliveredAudioMetadata(24_000))
    recorder.record_returned_frame(10.0)
    recorder.record_audio_duration(1.0)

    evidence = recorder.finish(
        session_duration_seconds=1.0,
        output_path=tmp_path / "measured-production.json",
    )

    assert evidence.output_width == 640
    assert evidence.output_height == 360
    assert evidence.audio_sample_rate_hz == 24_000


def test_recorder_does_not_promote_configured_hd_over_measured_sd(tmp_path) -> None:
    recorder = _recorder(tmp_path, output_width=1920, output_height=1080)
    recorder.record_delivered_video_metadata(DeliveredVideoMetadata(854, 480))
    for _ in range(30):
        recorder.record_returned_frame(10.0)
    recorder.record_audio_duration(1.0)

    evidence = recorder.finish(
        session_duration_seconds=1.0,
        output_path=tmp_path / "sd-production.json",
    )

    assert evidence.output_width == 854
    assert evidence.output_height == 480
