"""Rights and provenance validation for Seldrune Face training manifests."""
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True)
class IdentityRecord:
    subject_id: str
    consent_record: str
    rights_basis: str
    capture_ids: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    provenance: str
    split: DatasetSplit
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


def validate_identity(record: IdentityRecord, *, now: datetime | None = None) -> None:
    """Reject an identity that is not eligible for Seldrune-owned model training."""
    required = {
        "subject_id": record.subject_id,
        "consent_record": record.consent_record,
        "rights_basis": record.rights_basis,
        "provenance": record.provenance,
    }
    missing = tuple(name for name, value in required.items() if not value.strip())
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    if not record.capture_ids or any(not item.strip() for item in record.capture_ids):
        raise ValueError("capture_ids must contain immutable source identifiers")
    if "training" not in record.allowed_purposes:
        raise ValueError("consent does not permit training")
    if record.revoked_at is not None:
        raise ValueError("consent has been revoked")

    current = now or datetime.now(UTC)
    if record.expires_at is not None:
        expiry = record.expires_at
        if expiry.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if expiry <= current:
            raise ValueError("consent has expired")


def validate_manifest(records: tuple[IdentityRecord, ...]) -> None:
    """Validate records and ensure a subject cannot leak across dataset splits."""
    if not records:
        raise ValueError("dataset manifest cannot be empty")

    subject_splits: dict[str, DatasetSplit] = {}
    capture_ids: set[str] = set()
    for record in records:
        validate_identity(record)
        existing = subject_splits.get(record.subject_id)
        if existing is not None and existing != record.split:
            raise ValueError(f"subject {record.subject_id!r} crosses dataset splits")
        subject_splits[record.subject_id] = record.split

        overlap = capture_ids.intersection(record.capture_ids)
        if overlap:
            raise ValueError("capture IDs must be unique across the manifest")
        capture_ids.update(record.capture_ids)
