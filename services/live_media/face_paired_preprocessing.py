"""Convert admitted source/reference pairs into trainable tensors."""
from __future__ import annotations

from .face_paired_samples import build_identity_pairs
from .face_paired_training import PairedTrainingBatch
from .face_preprocessing import _load_rgb_tensor
from .face_training_bundle import FaceTrainingBundle


def build_paired_batches(
    bundle: FaceTrainingBundle,
    *,
    input_size: int = 256,
) -> tuple[PairedTrainingBatch, ...]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for paired preprocessing") from exc
    batches: list[PairedTrainingBatch] = []
    for pair in build_identity_pairs(bundle):
        source = _load_rgb_tensor(torch, pair.source_path, input_size).unsqueeze(0)
        reference = _load_rgb_tensor(torch, pair.reference_path, input_size).unsqueeze(0)
        # Same-identity cross-capture supervision: reconstruct the reference capture.
        batch = PairedTrainingBatch(source, reference, reference.clone())
        batch.validate()
        batches.append(batch)
    return tuple(batches)
