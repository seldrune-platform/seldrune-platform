"""Tests for evidence-backed Seldrune Face production promotion."""

from dataclasses import replace

import pytest

from services.live_media.face_production_gate import (
    FaceProductionEvidence,
    evaluate_production_gates,
)


def _evidence() -> FaceProductionEvidence:
    return FaceProductionEvidence(
        run_id="production-session-001",
        verification_receipt_sha256="a" * 64,
        frames_returned=300,
        session_duration_seconds=10.0,
        p95_latency_ms=90.0,
        output_width=1920,
        output_height=1080,
        audio_sample_rate_hz=48_000,
        audio_duration_seconds=10.0,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )


def test_measured_hd_face_and_voice_evidence_promotes_all_gates() -> None:
    gates = evaluate_production_gates(_evidence())

    assert gates.live_session_verified is True
    assert gates.mobile_hd_output_verified is True
    assert gates.voice_hd_output_verified is True


def test_slow_or_short_session_does_not_claim_production_verification() -> None:
    slow = evaluate_production_gates(replace(_evidence(), p95_latency_ms=151.0))
    short = evaluate_production_gates(replace(_evidence(), frames_returned=29))

    assert slow.live_session_verified is False
    assert short.live_session_verified is False
    assert slow.mobile_hd_output_verified is False
    assert short.voice_hd_output_verified is False


def test_non_hd_output_and_missing_audio_keep_specific_gates_pending() -> None:
    evidence = replace(
        _evidence(),
        output_width=640,
        output_height=480,
        audio_sample_rate_hz=None,
        audio_duration_seconds=None,
    )
    gates = evaluate_production_gates(evidence)

    assert gates.live_session_verified is True
    assert gates.mobile_hd_output_verified is False
    assert gates.voice_hd_output_verified is False


def test_gate_rejects_untrusted_or_malformed_evidence() -> None:
    with pytest.raises(ValueError, match="authorized identity"):
        evaluate_production_gates(replace(_evidence(), authorization_verified=False))
    with pytest.raises(ValueError, match="SHA-256"):
        evaluate_production_gates(replace(_evidence(), verification_receipt_sha256="not-a-hash"))
    with pytest.raises(ValueError, match="audio evidence"):
        evaluate_production_gates(replace(_evidence(), audio_duration_seconds=None))
