"""Tests for rights-gated Seldrune Face tensor batches."""
from datetime import UTC, datetime, timedelta

import pytest

torch = pytest.importorskip("torch")

from services.live_media.face_dataset import DatasetSplit, IdentityRecord
from services.live_media.face_tensor_batches import FaceTrainingSample, build_tensor_batches


def _identity(split: DatasetSplit = DatasetSplit.TRAIN) -> IdentityRecord:
    return IdentityRecord(
        subject_id="subject-001",
        consent_record="consent-001",
        rights_basis="explicit-consent",
        capture_ids=("capture-001", "capture-002"),
        allowed_purposes=("training", "evaluation"),
        provenance="seldrune-consented-capture",
        split=split,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )


def _sample(identity: IdentityRecord | None = None, capture_id: str = "capture-001") -> FaceTrainingSample:
    return FaceTrainingSample(
        identity=identity or _identity(),
        capture_id=capture_id,
        image=torch.zeros(3, 8, 8),
        identity_embedding=torch.zeros(512),
        target=torch.ones(3, 8, 8),
    )


def test_build_tensor_batches_stacks_admitted_samples() -> None:
    batches = build_tensor_batches([_sample(), _sample(capture_id="capture-002")], batch_size=2)
    image, embedding, target = batches[0]
    assert image.shape == (2, 3, 8, 8)
    assert embedding.shape == (2, 512)
    assert target.shape == (2, 3, 8, 8)


def test_rejects_non_training_split() -> None:
    with pytest.raises(ValueError, match="training-split"):
        build_tensor_batches([_sample(_identity(DatasetSplit.VALIDATION))], batch_size=1)


def test_rejects_capture_not_in_manifest() -> None:
    with pytest.raises(ValueError, match="capture_id"):
        build_tensor_batches([_sample(capture_id="capture-999")], batch_size=1)


def test_rejects_revoked_consent() -> None:
    identity = IdentityRecord(
        subject_id="subject-001",
        consent_record="consent-001",
        rights_basis="explicit-consent",
        capture_ids=("capture-001",),
        allowed_purposes=("training",),
        provenance="seldrune-consented-capture",
        split=DatasetSplit.TRAIN,
        revoked_at=datetime.now(UTC),
    )
    with pytest.raises(ValueError, match="revoked"):
        build_tensor_batches([_sample(identity)], batch_size=1)


def test_rejects_empty_samples_and_invalid_batch_size() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_tensor_batches([], batch_size=1)
    with pytest.raises(ValueError, match="batch_size"):
        build_tensor_batches([_sample()], batch_size=0)
