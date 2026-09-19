from datetime import UTC, datetime, timedelta

import pytest

from services.live_media.face_dataset import (
    DatasetSplit,
    IdentityRecord,
    validate_identity,
    validate_manifest,
)


def record(**changes: object) -> IdentityRecord:
    values = {
        "subject_id": "subject-001",
        "consent_record": "consent:sha256:abc",
        "rights_basis": "direct-consent",
        "capture_ids": ("capture:sha256:one",),
        "allowed_purposes": ("training", "evaluation"),
        "provenance": "authorized-capture-session",
        "split": DatasetSplit.TRAIN,
        "expires_at": datetime.now(UTC) + timedelta(days=30),
    }
    values.update(changes)
    return IdentityRecord(**values)


def test_authorized_identity_is_accepted() -> None:
    validate_identity(record())


def test_training_permission_is_required() -> None:
    with pytest.raises(ValueError, match="permit training"):
        validate_identity(record(allowed_purposes=("evaluation",)))


def test_revoked_consent_is_rejected() -> None:
    with pytest.raises(ValueError, match="revoked"):
        validate_identity(record(revoked_at=datetime.now(UTC)))


def test_subject_cannot_cross_splits() -> None:
    with pytest.raises(ValueError, match="crosses dataset splits"):
        validate_manifest(
            (
                record(),
                record(
                    split=DatasetSplit.TEST,
                    capture_ids=("capture:sha256:two",),
                ),
            )
        )


def test_capture_ids_are_unique() -> None:
    with pytest.raises(ValueError, match="unique"):
        validate_manifest(
            (
                record(),
                record(subject_id="subject-002"),
            )
        )
