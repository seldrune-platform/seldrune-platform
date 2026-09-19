"""Rights-gated tensor batch construction for Seldrune Face training."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from services.live_media.face_dataset import (
    DatasetSplit,
    IdentityRecord,
    validate_identity,
)


@dataclass(frozen=True)
class FaceTrainingSample:
    identity: IdentityRecord
    capture_id: str
    image: Any
    identity_embedding: Any
    target: Any

    def validate(self) -> None:
        validate_identity(self.identity)
        if self.identity.split is not DatasetSplit.TRAIN:
            raise ValueError("only training-split identities may enter training batches")
        if self.capture_id not in self.identity.capture_ids:
            raise ValueError("sample capture_id is not admitted by the identity manifest")
        for name, value in (
            ("image", self.image),
            ("identity_embedding", self.identity_embedding),
            ("target", self.target),
        ):
            if value is None:
                raise ValueError(f"{name} tensor is required")


def build_tensor_batches(
    samples: Iterable[FaceTrainingSample],
    *,
    batch_size: int,
) -> list[tuple[Any, Any, Any]]:
    """Stack admitted samples into batches consumed by the CUDA training loop."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to construct Face training batches") from exc

    admitted = list(samples)
    if not admitted:
        raise ValueError("at least one admitted training sample is required")
    for sample in admitted:
        sample.validate()

    batches: list[tuple[Any, Any, Any]] = []
    for start in range(0, len(admitted), batch_size):
        chunk = admitted[start : start + batch_size]
        batches.append(
            (
                torch.stack([sample.image for sample in chunk]),
                torch.stack([sample.identity_embedding for sample in chunk]),
                torch.stack([sample.target for sample in chunk]),
            )
        )
    return batches
