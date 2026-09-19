"""Tests for reference-image conditioned Face v0.1."""
import pytest

from services.live_media.face_architecture import default_face_architecture
from services.live_media.face_reference_model import build_reference_conditioned_model


def test_reference_model_preserves_image_geometry() -> None:
    torch = pytest.importorskip("torch")
    model = build_reference_conditioned_model(default_face_architecture())
    source = torch.rand(1, 3, 128, 128)
    reference = torch.rand(1, 3, 128, 128)
    output = model(source, reference)
    assert output.shape == source.shape
