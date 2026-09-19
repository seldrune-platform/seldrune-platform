"""Tests for durable Face verification receipt I/O and CLI reporting."""

from dataclasses import asdict
import json

import pytest

from services.live_media.face_inference_evidence import FaceInferenceEvidence
from services.live_media.face_output_manifest import FaceOutputManifest
from services.live_media.face_stream_gate import FaceStreamEvidence
from services.live_media.face_verification_io import (
    load_verification_receipt,
    write_verification_receipt,
)
from services.live_media.face_verification_receipt import FaceVerificationReceipt
from services.live_media.face_verify import verify_receipt_file


def _receipt() -> FaceVerificationReceipt:
    model_digest = "c" * 64
    return FaceVerificationReceipt(
        run_id="gpu-run-verified-001",
        output=FaceOutputManifest("seldrune-face-v0.1", "a" * 64, "b" * 64, model_digest),
        inference=FaceInferenceEvidence(model_digest, "d" * 64, "e" * 64, 18.0),
        stream=FaceStreamEvidence(120, 118, 4.0, 19.0),
        reference_sha256="f" * 64,
        identity_similarity=0.9,
        frame_change_ratio=0.2,
        authorization_verified=True,
        synthetic_media_indicator_verified=True,
    )


def test_receipt_round_trip_is_verified(tmp_path) -> None:
    path = write_verification_receipt(_receipt(), tmp_path / "receipt.json")
    loaded = load_verification_receipt(path)
    assert loaded == _receipt()
    summary = verify_receipt_file(path)
    assert summary["status"] == "verified"
    assert summary["frames_transformed"] == 118


def test_loader_rejects_missing_evidence_field(tmp_path) -> None:
    payload = asdict(_receipt())
    del payload["reference_sha256"]
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        load_verification_receipt(path)


def test_loader_rejects_string_authorization_flag(tmp_path) -> None:
    payload = asdict(_receipt())
    payload["authorization_verified"] = "true"
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="booleans"):
        load_verification_receipt(path)


def test_writer_refuses_unverified_receipt(tmp_path) -> None:
    payload = asdict(_receipt())
    payload["identity_similarity"] = 0.1
    invalid = FaceVerificationReceipt(
        output=FaceOutputManifest(**payload.pop("output")),
        inference=FaceInferenceEvidence(**payload.pop("inference")),
        stream=FaceStreamEvidence(**payload.pop("stream")),
        **payload,
    )
    with pytest.raises(ValueError, match="identity similarity"):
        write_verification_receipt(invalid, tmp_path / "receipt.json")
