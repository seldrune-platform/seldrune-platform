"""Tests for the unified Seldrune Face real-output proof receipt."""

from dataclasses import replace

import pytest

from services.live_media.face_inference_evidence import FaceInferenceEvidence
from services.live_media.face_output_manifest import FaceOutputManifest
from services.live_media.face_stream_gate import FaceStreamEvidence
from services.live_media.face_verification_receipt import (
    FaceVerificationReceipt,
    verify_real_output,
)


def _receipt() -> FaceVerificationReceipt:
    model_digest = "c" * 64
    return FaceVerificationReceipt(
        run_id="face-verify-001",
        output=FaceOutputManifest(
            model_version="seldrune-face-v0.1",
            checkpoint_sha256="a" * 64,
            dataset_manifest_sha256="b" * 64,
            onnx_sha256=model_digest,
        ),
        inference=FaceInferenceEvidence(
            model_sha256=model_digest,
            input_sha256="d" * 64,
            output_sha256="e" * 64,
            inference_ms=20.0,
        ),
        stream=FaceStreamEvidence(
            frames_processed=100,
            frames_transformed=98,
            duration_seconds=4.0,
            average_inference_ms=21.0,
        ),
        reference_sha256="f" * 64,
        identity_similarity=0.88,
        frame_change_ratio=0.24,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )


def test_verified_receipt_binds_all_real_output_evidence() -> None:
    receipt = _receipt()
    assert verify_real_output(receipt) is receipt


def test_receipt_rejects_model_manifest_mismatch() -> None:
    receipt = _receipt()
    mismatched = replace(
        receipt,
        inference=replace(receipt.inference, model_sha256="9" * 64),
    )
    with pytest.raises(ValueError, match="does not match"):
        mismatched.validate()


def test_receipt_rejects_unchanged_or_excessively_changed_frame() -> None:
    with pytest.raises(ValueError, match="frame-change"):
        replace(_receipt(), frame_change_ratio=0.0).validate()
    with pytest.raises(ValueError, match="frame-change"):
        replace(_receipt(), frame_change_ratio=0.99).validate()


def test_receipt_rejects_identity_below_threshold() -> None:
    with pytest.raises(ValueError, match="identity similarity"):
        replace(_receipt(), identity_similarity=0.5).validate()


def test_receipt_rejects_partial_stream_transformation() -> None:
    receipt = _receipt()
    weak_stream = replace(receipt.stream, frames_transformed=50)
    with pytest.raises(ValueError, match="transformed-frame ratio"):
        replace(receipt, stream=weak_stream).validate()


def test_receipt_requires_authorization_and_disclosure() -> None:
    with pytest.raises(ValueError, match="authorized identity"):
        replace(_receipt(), authorization_verified=False).validate()
    with pytest.raises(ValueError, match="synthetic-media indicator"):
        replace(_receipt(), synthetic_media_indicator_verified=False).validate()
