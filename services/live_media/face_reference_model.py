"""Reference-image conditioned wrapper for Seldrune Face v0.1."""
from __future__ import annotations

from typing import Any

from .face_architecture import FaceArchitecture
from .face_reference_encoder import build_reference_encoder
from .face_torch_model import build_face_model


def build_reference_conditioned_model(architecture: FaceArchitecture) -> Any:
    architecture.validate()
    try:
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for Face v0.1") from exc

    class ReferenceConditionedFace(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.reference_encoder = build_reference_encoder(architecture)
            self.transform = build_face_model(architecture)

        def forward(self, source_image: Any, reference_image: Any) -> Any:
            identity = self.reference_encoder(reference_image)
            return self.transform(source_image, identity)

    return ReferenceConditionedFace()
