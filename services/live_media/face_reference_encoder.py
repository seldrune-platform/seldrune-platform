"""Seldrune-owned visual identity encoder for Face v0.1."""
from __future__ import annotations

from typing import Any

from .face_architecture import FaceArchitecture


def build_reference_encoder(architecture: FaceArchitecture) -> Any:
    architecture.validate()
    try:
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for the Face reference encoder") from exc

    class FaceReferenceEncoder(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            width = architecture.encoder_width
            self.features = nn.Sequential(
                nn.Conv2d(3, width, 5, stride=2, padding=2),
                nn.SiLU(),
                nn.Conv2d(width, width * 2, 3, stride=2, padding=1),
                nn.SiLU(),
                nn.AdaptiveAvgPool2d(1),
            )
            self.projection = nn.Linear(width * 2, architecture.identity_embedding_dim)

        def forward(self, reference_image: Any) -> Any:
            features = self.features(reference_image).flatten(1)
            return self.projection(features)

    return FaceReferenceEncoder()
