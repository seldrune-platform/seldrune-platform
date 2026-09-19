"""Tests for the first-real-output evidence gate."""
import pytest

from services.live_media.face_artifact_manifest import FaceArtifactManifest
from services.live_media.face_output_gate import FaceOutputEvidence


def _artifact() -> FaceArtifactManifest:
    return FaceArtifactManifest("seldrune-face-v0.1", "a" * 64, "b" * 64, "c" * 64)


def test_output_gate_accepts_measured_transform() -> None:
    FaceOutputEvidence(_artifact(), True, True, 12.5).validate()


def test_output_gate_rejects_untransformed_frame() -> None:
    with pytest.raises(ValueError, match="transformed"):
        FaceOutputEvidence(_artifact(), True, False, 12.5).validate()
