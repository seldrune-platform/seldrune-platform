import pytest

from services.live_media.realism_quality_gate import (
    FaceRealismEvidence,
    RealismEvidenceError,
    RealismQualityPolicy,
    VoiceRealismEvidence,
    validate_av_drift,
    validate_face_realism,
    validate_voice_realism,
)


def policy(**overrides):
    values = {
        "face_min_identity_similarity": 0.8,
        "face_min_temporal_consistency": 0.8,
        "face_min_blend_quality": 0.8,
        "voice_min_speaker_similarity": 0.8,
        "voice_min_content_preservation": 0.9,
        "voice_min_naturalness": 0.75,
        "voice_max_clipped_fraction": 0.001,
        "voice_max_dropout_fraction": 0.001,
        "max_processing_p95_ms": 150.0,
        "max_av_drift_ms": 80.0,
    }
    values.update(overrides)
    return RealismQualityPolicy(**values)


def test_face_gate_requires_windowed_hd_output_and_all_realism_metrics():
    evidence = FaceRealismEvidence(
        evaluator_id="face-eval",
        evaluator_version="2.1",
        window_frames=30,
        output_width=1280,
        output_height=720,
        output_fps=30.0,
        identity_similarity=0.92,
        temporal_consistency=0.91,
        blend_quality=0.88,
        p95_inference_ms=110.0,
    )
    report = validate_face_realism(evidence, policy())
    assert report["media_kind"] == "video"
    assert report["evaluator_version"] == "2.1"


def test_face_gate_accepts_full_hd_portrait_orientation():
    evidence = FaceRealismEvidence(
        evaluator_id="face-eval",
        evaluator_version="2.1",
        window_frames=30,
        output_width=1080,
        output_height=1920,
        output_fps=30.0,
        identity_similarity=0.92,
        temporal_consistency=0.91,
        blend_quality=0.88,
        p95_inference_ms=110.0,
    )
    report = validate_face_realism(evidence, policy())
    assert (report["output_width"], report["output_height"]) == (1080, 1920)


@pytest.mark.parametrize(
    "changes",
    [
        {"window_frames": 1},
        {"output_width": 640},
        {"output_fps": 24.0},
        {"identity_similarity": 0.79},
        {"temporal_consistency": 0.79},
        {"blend_quality": 0.79},
        {"p95_inference_ms": 151.0},
    ],
)
def test_face_gate_rejects_quality_or_format_below_policy(changes):
    values = {
        "evaluator_id": "face-eval",
        "evaluator_version": "2.1",
        "window_frames": 30,
        "output_width": 1280,
        "output_height": 720,
        "output_fps": 30.0,
        "identity_similarity": 0.92,
        "temporal_consistency": 0.91,
        "blend_quality": 0.88,
        "p95_inference_ms": 110.0,
    }
    values.update(changes)
    with pytest.raises(RealismEvidenceError):
        validate_face_realism(FaceRealismEvidence(**values), policy())


def test_voice_gate_checks_hifi_content_identity_naturalness_and_artifacts():
    evidence = VoiceRealismEvidence(
        evaluator_id="voice-eval",
        evaluator_version="1.4",
        window_duration_seconds=1.2,
        sample_rate_hz=48000,
        channels=1,
        speaker_similarity=0.9,
        content_preservation=0.96,
        naturalness=0.84,
        clipped_fraction=0.0001,
        dropout_fraction=0.0002,
        p95_processing_ms=120.0,
    )
    report = validate_voice_realism(evidence, policy())
    assert report["media_kind"] == "audio"
    assert report["sample_rate_hz"] == 48000


@pytest.mark.parametrize(
    "changes",
    [
        {"window_duration_seconds": 0.5},
        {"sample_rate_hz": 44100},
        {"speaker_similarity": 0.79},
        {"content_preservation": 0.89},
        {"naturalness": 0.74},
        {"clipped_fraction": 0.002},
        {"dropout_fraction": 0.002},
        {"p95_processing_ms": 151.0},
    ],
)
def test_voice_gate_rejects_quality_or_format_below_policy(changes):
    values = {
        "evaluator_id": "voice-eval",
        "evaluator_version": "1.4",
        "window_duration_seconds": 1.2,
        "sample_rate_hz": 48000,
        "channels": 1,
        "speaker_similarity": 0.9,
        "content_preservation": 0.96,
        "naturalness": 0.84,
        "clipped_fraction": 0.0001,
        "dropout_fraction": 0.0002,
        "p95_processing_ms": 120.0,
    }
    values.update(changes)
    with pytest.raises(RealismEvidenceError):
        validate_voice_realism(VoiceRealismEvidence(**values), policy())


def test_evidence_rejects_nan_and_unversioned_quality_sources():
    with pytest.raises(RealismEvidenceError, match="range"):
        FaceRealismEvidence(
            "face-eval", "1", 30, 1280, 720, 30.0, float("nan"), 0.9, 0.9, 50.0
        ).validate()
    with pytest.raises(RealismEvidenceError, match="versioned"):
        VoiceRealismEvidence(
            "voice-eval", "", 1.0, 48000, 1, 0.9, 0.9, 0.9, 0.0, 0.0, 50.0
        ).validate()


def test_policy_json_requires_explicit_perceptual_thresholds():
    with pytest.raises(RealismEvidenceError, match="missing or unknown"):
        RealismQualityPolicy.from_json('{"max_av_drift_ms": 80.0}')


def test_av_sync_gate_accepts_within_limit_and_rejects_drift():
    active = policy()
    assert validate_av_drift(1000, 940, active)["drift_ms"] == 60
    with pytest.raises(RealismEvidenceError, match="drift"):
        validate_av_drift(1000, 900, active)
