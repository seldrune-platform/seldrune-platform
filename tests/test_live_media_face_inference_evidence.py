"""Tests for Face inference evidence."""
import pytest

from services.live_media.face_inference_evidence import FaceInferenceEvidence


def test_rejects_unchanged_output() -> None:
    evidence = FaceInferenceEvidence("a" * 64, "b" * 64, "b" * 64, 10.0)
    with pytest.raises(ValueError, match="differ"):
        evidence.validate()
