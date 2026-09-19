"""Preflight gate that turns a rights-cleared manifest into a GPU training job."""
from dataclasses import dataclass
from hashlib import sha256
import json

from .face_dataset import IdentityRecord, validate_manifest
from .face_training import FaceTrainingConfig


@dataclass(frozen=True)
class FaceTrainingJob:
    job_id: str
    model_version: str
    accelerator: str
    manifest_sha256: str
    subject_count: int
    capture_count: int
    config: FaceTrainingConfig


def manifest_digest(records: tuple[IdentityRecord, ...]) -> str:
    payload = [
        {
            "subject_id": record.subject_id,
            "consent_record": record.consent_record,
            "rights_basis": record.rights_basis,
            "capture_ids": list(record.capture_ids),
            "allowed_purposes": list(record.allowed_purposes),
            "provenance": record.provenance,
            "split": record.split.value,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
        }
        for record in records
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def prepare_training_job(
    records: tuple[IdentityRecord, ...],
    config: FaceTrainingConfig,
) -> FaceTrainingJob:
    """Validate rights/config before a job can be admitted to GPU execution."""
    validate_manifest(records)
    config.validate()
    digest = manifest_digest(records)
    subjects = {record.subject_id for record in records}
    captures = sum(len(record.capture_ids) for record in records)
    return FaceTrainingJob(
        job_id=f"{config.model_version}:{digest[:12]}",
        model_version=config.model_version,
        accelerator=config.accelerator,
        manifest_sha256=digest,
        subject_count=len(subjects),
        capture_count=captures,
        config=config,
    )
