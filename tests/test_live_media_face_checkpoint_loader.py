"""Tests for Face checkpoint integrity enforcement."""
import pytest

from services.live_media.face_checkpoint_loader import load_verified_checkpoint


def test_checkpoint_loader_rejects_wrong_digest(tmp_path) -> None:
    path = tmp_path / "checkpoint.pt"
    path.write_bytes(b"not-a-checkpoint")
    with pytest.raises(ValueError, match="SHA-256"):
        load_verified_checkpoint(object(), path, expected_sha256="0" * 64)
