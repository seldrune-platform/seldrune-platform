"""Preflight guard for real Seldrune Face GPU training."""
from dataclasses import dataclass

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_training_bundle import FaceTrainingBundle


@dataclass(frozen=True)
class FaceTrainingAdmission:
    capture_count: int
    training_subject_count: int
    execution_digest: str


def admit_face_training(
    execution: GpuTrainingExecution,
    bundle: FaceTrainingBundle,
) -> FaceTrainingAdmission:
    execution.validate()
    bundle.validate()
    subjects = {record.subject_id for record in bundle.records if record.split.value == "train"}
    captures = sum(
        len(record.capture_ids) for record in bundle.records if record.split.value == "train"
    )
    if not subjects or not captures:
        raise ValueError("real GPU training requires admitted training subjects and captures")
    return FaceTrainingAdmission(captures, len(subjects), execution.digest())
