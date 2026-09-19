from services.live_media.face_dataset import DatasetSplit, IdentityRecord
from services.live_media.face_training import default_training_config
from services.live_media.face_training_runner import (
    manifest_digest,
    prepare_training_job,
)


def records() -> tuple[IdentityRecord, ...]:
    return (
        IdentityRecord(
            subject_id="subject-001",
            consent_record="consent:001",
            rights_basis="direct-consent",
            capture_ids=("capture:001", "capture:002"),
            allowed_purposes=("training", "evaluation"),
            provenance="authorized-capture-session",
            split=DatasetSplit.TRAIN,
        ),
    )


def test_preflight_creates_reproducible_gpu_job() -> None:
    manifest = records()
    job = prepare_training_job(manifest, default_training_config())
    assert job.accelerator == "rtx-pro-6000-blackwell"
    assert job.manifest_sha256 == manifest_digest(manifest)
    assert job.subject_count == 1
    assert job.capture_count == 2
    assert job.job_id.startswith("seldrune-face-v0.1:")


def test_manifest_digest_is_deterministic() -> None:
    manifest = records()
    assert manifest_digest(manifest) == manifest_digest(manifest)
