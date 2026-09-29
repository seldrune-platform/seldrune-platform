"""Batch construction for reference-conditioned Seldrune Face v0.1 training."""

from __future__ import annotations

from collections.abc import Iterable

from .face_paired_training import PairedTrainingBatch
from .face_tensor_batches import FaceTrainingSample


def build_paired_batches(
    samples: Iterable[FaceTrainingSample], *, batch_size: int
) -> list[PairedTrainingBatch]:
    """Reject captures until a supervised identity-transfer target is admitted.

    FaceTrainingSample currently has one identity and no target identity or
    capture provenance. Preprocessing sets target=image, so the old batcher
    could only supervise reconstruction of the source. A same-subject
    reference does not establish a source-to-different-identity target.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    admitted = list(samples)
    if not admitted:
        raise ValueError("at least one admitted training sample is required")
    for sample in admitted:
        sample.validate()
    raise ValueError(
        "identity-transfer training requires an admitted cross-identity target "
        "with source, reference, and target provenance; FaceTrainingSample "
        "contains no such pairing"
    )
