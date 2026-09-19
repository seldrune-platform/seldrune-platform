"""Tests for the Seldrune-owned visual identity encoder."""
import pytest

torch = pytest.importorskip("torch")

from services.live_media.face_architecture import default_face_architecture
from services.live_media.face_reference_encoder import build_reference_encoder


def test_reference_encoder_outputs_identity_vector() -> None:
    architecture = default_face_architecture()
    encoder = build_reference_encoder(architecture)
    image = torch.rand(2, 3, 128, 128)
    output = encoder(image)
    assert output.shape == (2, architecture.identity_embedding_dim)
