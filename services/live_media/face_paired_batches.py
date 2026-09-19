"""Batch construction for reference-conditioned Seldrune Face v0.1 training."""
from __future__ import annotations
from collections.abc import Iterable
from typing import Any
from .face_paired_training import PairedTrainingBatch
from .face_tensor_batches import FaceTrainingSample

def build_paired_batches(samples: Iterable[FaceTrainingSample], *, batch_size: int) -> list[PairedTrainingBatch]:
    """Pair each admitted source with another admitted capture of the same identity."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to construct paired Face batches") from exc
    admitted = list(samples)
    if not admitted:
        raise ValueError("at least one admitted training sample is required")
    for sample in admitted:
        sample.validate()
    by_subject: dict[str, list[FaceTrainingSample]] = {}
    for sample in admitted:
        by_subject.setdefault(sample.identity.subject_id, []).append(sample)
    pairs: list[tuple[Any, Any, Any]] = []
    for sample in admitted:
        candidates = by_subject[sample.identity.subject_id]
        index = candidates.index(sample)
        reference = candidates[(index + 1) % len(candidates)]
        pairs.append((sample.image, reference.image, sample.target))
    batches = []
    for start in range(0, len(pairs), batch_size):
        chunk = pairs[start:start + batch_size]
        batches.append(PairedTrainingBatch(
            source=torch.stack([item[0] for item in chunk]),
            reference=torch.stack([item[1] for item in chunk]),
            target=torch.stack([item[2] for item in chunk]),
        ))
    return batches
