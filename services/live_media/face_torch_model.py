"""Optional PyTorch implementation boundary for Seldrune Face v0.1."""
from __future__ import annotations

from typing import Any

from .face_architecture import FaceArchitecture


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def build_face_model(architecture: FaceArchitecture) -> Any:
    """Build an untrained Seldrune-owned identity-conditioned RGB network."""
    architecture.validate()
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to build Seldrune Face v0.1") from exc

    class SeldruneFaceV01(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            width = architecture.encoder_width
            self.encoder = nn.Sequential(
                nn.Conv2d(architecture.input_channels, width, 3, padding=1),
                nn.SiLU(),
                nn.Conv2d(width, architecture.bottleneck_width, 3, padding=1),
                nn.SiLU(),
            )
            self.identity = nn.Linear(
                architecture.identity_embedding_dim,
                architecture.bottleneck_width,
            )
            self.decoder = nn.Sequential(
                nn.Conv2d(
                    architecture.bottleneck_width,
                    architecture.decoder_width,
                    3,
                    padding=1,
                ),
                nn.SiLU(),
                nn.Conv2d(
                    architecture.decoder_width,
                    architecture.output_channels,
                    3,
                    padding=1,
                ),
                nn.Sigmoid(),
            )

        def forward(self, image: Any, identity_embedding: Any) -> Any:
            features = self.encoder(image)
            identity = self.identity(identity_embedding).unsqueeze(-1).unsqueeze(-1)
            return self.decoder(features + identity)

    return SeldruneFaceV01()
