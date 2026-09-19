"""Preprocess admitted Face captures into tensors without third-party face-swap weights."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from services.live_media.face_dataset import DatasetSplit, IdentityRecord
from services.live_media.face_tensor_batches import FaceTrainingSample
from services.live_media.face_training_bundle import FaceTrainingBundle


@dataclass(frozen=True)
class PreprocessedFaceDataset:
    samples: tuple[FaceTrainingSample, ...]
    input_size: int


def _identity_embedding(torch: Any, subject_id: str, dimensions: int = 512) -> Any:
    """Create deterministic identity conditioning from a pseudonymous subject ID."""
    digest = sha256(subject_id.encode("utf-8")).digest()
    values = [((digest[index % len(digest)] / 255.0) * 2.0) - 1.0 for index in range(dimensions)]
    return torch.tensor(values, dtype=torch.float32)


def _load_rgb_tensor(torch: Any, path: Path, input_size: int) -> Any:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for Face capture preprocessing") from exc
    with Image.open(path) as image:
        rgb = image.convert("RGB").resize((input_size, input_size))
        data = torch.tensor(list(rgb.getdata()), dtype=torch.float32)
    return data.reshape(input_size, input_size, 3).permute(2, 0, 1) / 255.0


def preprocess_training_bundle(
    bundle: FaceTrainingBundle,
    *,
    input_size: int = 256,
) -> PreprocessedFaceDataset:
    if input_size < 128 or input_size % 32:
        raise ValueError("input_size must be >=128 and divisible by 32")
    bundle.validate()
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for Face preprocessing") from exc

    samples: list[FaceTrainingSample] = []
    for identity in bundle.records:
        if identity.split is not DatasetSplit.TRAIN:
            continue
        embedding = _identity_embedding(torch, identity.subject_id)
        for capture_id in identity.capture_ids:
            image = _load_rgb_tensor(torch, bundle.capture_paths[capture_id], input_size)
            samples.append(
                FaceTrainingSample(
                    identity=identity,
                    capture_id=capture_id,
                    image=image,
                    identity_embedding=embedding.clone(),
                    target=image.clone(),
                )
            )
    if not samples:
        raise ValueError("training bundle contains no admitted training captures")
    return PreprocessedFaceDataset(samples=tuple(samples), input_size=input_size)
