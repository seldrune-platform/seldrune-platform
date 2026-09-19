"""Tests for Face real-training admission."""
import pytest

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_training_bundle import FaceTrainingBundle
from services.live_media.face_training_guard import admit_face_training


def test_empty_bundle_is_not_admitted() -> None:
    execution = GpuTrainingExecution(
        job_id="job",
        model_version="seldrune-face-v0.1",
        accelerator="gpu",
        dataset_manifest_sha256="a" * 64,
        max_steps=1,
        checkpoint_every=1,
        precision="bf16",
        output_dir="/tmp",
    )
    with pytest.raises(ValueError):
        admit_face_training(execution, FaceTrainingBundle((), {}))
