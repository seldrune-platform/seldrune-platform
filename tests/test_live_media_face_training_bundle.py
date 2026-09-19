"""Tests for rights-gated Face training bundles."""
import json

import pytest

from services.live_media.face_training_bundle import load_training_bundle


def test_bundle_requires_exact_capture_mapping(tmp_path) -> None:
    capture = tmp_path / "face.bin"
    capture.write_bytes(b"capture")
    manifest = {
        "identities": [{
            "subject_id": "subject-1",
            "consent_record": "consent-1",
            "rights_basis": "explicit-consent",
            "capture_ids": ["capture-1"],
            "allowed_purposes": ["training"],
            "provenance": "consented-capture",
            "split": "train",
        }],
        "captures": {"capture-1": "face.bin"},
    }
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    bundle = load_training_bundle(path)
    assert bundle.capture_paths["capture-1"] == capture.resolve()


def test_bundle_rejects_missing_capture(tmp_path) -> None:
    manifest = {
        "identities": [{
            "subject_id": "subject-1",
            "consent_record": "consent-1",
            "rights_basis": "explicit-consent",
            "capture_ids": ["capture-1"],
            "allowed_purposes": ["training"],
            "provenance": "consented-capture",
            "split": "train",
        }],
        "captures": {"capture-1": "missing.bin"},
    }
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        load_training_bundle(path)
