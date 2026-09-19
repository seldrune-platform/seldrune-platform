"""Audit summary for admitted Face training bundles."""
from __future__ import annotations
from dataclasses import dataclass
from services.live_media.face_training_bundle import FaceTrainingBundle

@dataclass(frozen=True)
class DatasetAudit:
    subjects: int
    captures: int
    training_subjects: int

def audit_bundle(bundle: FaceTrainingBundle) -> DatasetAudit:
    bundle.validate()
    return DatasetAudit(
        subjects=len({r.subject_id for r in bundle.records}),
        captures=sum(len(r.capture_ids) for r in bundle.records),
        training_subjects=len({r.subject_id for r in bundle.records if r.split.value=="train"}),
    )
