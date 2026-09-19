"""Tests for Face artifact evidence manifests."""
import pytest

from services.live_media.face_artifact_manifest import FaceArtifactManifest


def test_artifact_manifest_validates_chain() -> None:
    manifest = FaceArtifactManifest("seldrune-face-v0.1", "a" * 64, "b" * 64, "c" * 64)
    manifest.validate()


def test_artifact_manifest_rejects_invalid_digest() -> None:
    manifest = FaceArtifactManifest("seldrune-face-v0.1", "bad", "b" * 64, "c" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        manifest.validate()
