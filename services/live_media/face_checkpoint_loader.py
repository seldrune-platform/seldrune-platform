"""Verified checkpoint loader for Seldrune Face v0.1."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from services.live_media.face_training_executor import sha256_file


def load_verified_checkpoint(
    model: Any,
    checkpoint_path: str | Path,
    *,
    expected_sha256: str,
    device: str = "cpu",
) -> dict[str, Any]:
    path = Path(checkpoint_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if len(expected_sha256) != 64 or actual != expected_sha256:
        raise ValueError("checkpoint SHA-256 verification failed")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to load Face checkpoints") from exc
    payload = torch.load(path, map_location=device, weights_only=True)
    model.load_state_dict(payload["model_state_dict"])
    return payload
