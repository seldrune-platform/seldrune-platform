"""Tests for source/reference pairing without external face-swap weights."""

import pytest

from services.live_media.face_paired_batches import build_paired_batches


def test_paired_batches_reject_empty_dataset() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_paired_batches([], batch_size=1)


def test_paired_batches_reject_invalid_batch_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        build_paired_batches([], batch_size=0)


def test_same_identity_capture_cannot_claim_transfer_training() -> None:
    from services.live_media.face_dataset import DatasetSplit, IdentityRecord
    from services.live_media.face_tensor_batches import FaceTrainingSample

    identity = IdentityRecord(
        subject_id="fictional-subject",
        consent_record="synthetic-fixture",
        rights_basis="synthetic",
        capture_ids=("capture-1", "capture-2"),
        allowed_purposes=("training",),
        provenance="synthetic-test-only",
        split=DatasetSplit.TRAIN,
    )
    source = object()
    reference = object()
    samples = [
        FaceTrainingSample(identity, "capture-1", source, object(), source),
        FaceTrainingSample(identity, "capture-2", reference, object(), reference),
    ]
    with pytest.raises(ValueError, match="cross-identity target"):
        build_paired_batches(samples, batch_size=2)
