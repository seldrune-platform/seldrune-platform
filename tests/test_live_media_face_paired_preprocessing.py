"""The alternate same-identity bundle path cannot claim transfer training."""

import pytest

from services.live_media.face_dataset import DatasetSplit, IdentityRecord
from services.live_media.face_paired_preprocessing import build_paired_batches
from services.live_media.face_training_bundle import FaceTrainingBundle


def test_same_identity_reference_as_target_rejected_before_tensor_loading(tmp_path) -> None:
    first = tmp_path / "fictional-1.jpg"
    second = tmp_path / "fictional-2.jpg"
    first.write_bytes(b"synthetic fixture")
    second.write_bytes(b"synthetic fixture")
    identity = IdentityRecord(
        subject_id="fictional-subject",
        consent_record="synthetic-fixture",
        rights_basis="synthetic",
        capture_ids=("capture-1", "capture-2"),
        allowed_purposes=("training",),
        provenance="synthetic-test-only",
        split=DatasetSplit.TRAIN,
    )
    bundle = FaceTrainingBundle(
        records=(identity,),
        capture_paths={"capture-1": first, "capture-2": second},
    )
    with pytest.raises(ValueError, match="same-subject pairs are insufficient"):
        build_paired_batches(bundle)
