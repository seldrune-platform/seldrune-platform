"""Tests for cryptographically bound Face production evidence."""

import json

import pytest

from services.live_media.face_production_io import load_production_gates
from services.live_media.face_production_verify import verify_production_files
from services.live_media.face_training_executor import sha256_file


def _receipt_payload() -> dict[str, object]:
    model_digest = "c" * 64
    return {
        "run_id": "face-verify-001",
        "output": {
            "model_version": "seldrune-face-v0.1",
            "checkpoint_sha256": "a" * 64,
            "dataset_manifest_sha256": "b" * 64,
            "onnx_sha256": model_digest,
        },
        "inference": {
            "model_sha256": model_digest,
            "input_sha256": "d" * 64,
            "output_sha256": "e" * 64,
            "inference_ms": 20.0,
        },
        "stream": {
            "frames_processed": 300,
            "frames_transformed": 300,
            "duration_seconds": 10.0,
            "average_inference_ms": 21.0,
        },
        "reference_sha256": "f" * 64,
        "identity_similarity": 0.88,
        "frame_change_ratio": 0.24,
        "authorization_verified": True,
        "synthetic_media_indicator_verified": True,
    }


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_matching_receipts_unlock_measured_product_gates(tmp_path) -> None:
    receipt_path = tmp_path / "face-verification.json"
    evidence_path = tmp_path / "face-production.json"
    _write_json(receipt_path, _receipt_payload())
    _write_json(
        evidence_path,
        {
            "run_id": "production-session-001",
            "verification_receipt_sha256": sha256_file(receipt_path),
            "frames_returned": 300,
            "session_duration_seconds": 10.0,
            "p95_latency_ms": 90.0,
            "output_width": 1920,
            "output_height": 1080,
            "audio_sample_rate_hz": 48_000,
            "audio_duration_seconds": 10.0,
            "authorization_verified": True,
            "synthetic_media_indicator_verified": True,
        },
    )

    gates = load_production_gates(evidence_path, receipt_path)

    assert gates.live_session_verified is True
    assert gates.mobile_hd_output_verified is True
    assert gates.voice_hd_output_verified is True
    summary = verify_production_files(evidence_path, receipt_path)
    assert summary == {
        "status": "verified",
        "live_session_verified": True,
        "mobile_hd_output_verified": True,
        "voice_hd_output_verified": True,
    }


def test_mismatched_receipt_cannot_unlock_product_gates(tmp_path) -> None:
    receipt_path = tmp_path / "face-verification.json"
    evidence_path = tmp_path / "face-production.json"
    _write_json(receipt_path, _receipt_payload())
    _write_json(
        evidence_path,
        {
            "run_id": "production-session-001",
            "verification_receipt_sha256": "9" * 64,
            "frames_returned": 300,
            "session_duration_seconds": 10.0,
            "p95_latency_ms": 90.0,
            "output_width": 1920,
            "output_height": 1080,
            "audio_sample_rate_hz": None,
            "audio_duration_seconds": None,
            "authorization_verified": True,
            "synthetic_media_indicator_verified": True,
        },
    )

    with pytest.raises(ValueError, match="does not match"):
        load_production_gates(evidence_path, receipt_path)
