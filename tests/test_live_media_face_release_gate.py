"""Tests for Face v0.1 LiveShift release gating."""
import pytest

from services.live_media.face_artifact_manifest import FaceArtifactManifest
from services.live_media.face_output_gate import FaceOutputEvidence
from services.live_media.face_release_gate import FaceReleaseGate


def _output() -> FaceOutputEvidence:
    artifact = FaceArtifactManifest("seldrune-face-v0.1", "a" * 64, "b" * 64, "c" * 64)
    return FaceOutputEvidence(artifact, True, True, 10.0)


def test_release_gate_requires_stream_and_authorization() -> None:
    FaceReleaseGate(_output(), True, True).validate()
    with pytest.raises(ValueError, match="continuous"):
        FaceReleaseGate(_output(), False, True).validate()
    with pytest.raises(ValueError, match="authorized"):
        FaceReleaseGate(_output(), True, False).validate()
