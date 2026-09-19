"""Tests for admitted Face GPU execution to training-loop bridge."""
import pytest

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_training_bridge import execution_to_training_job


def _execution() -> GpuTrainingExecution:
    return GpuTrainingExecution(
        job_id="face-job-bridge-001",
        model_version="seldrune-face-v0.1",
        accelerator="rtx-pro-6000-blackwell",
        dataset_manifest_sha256="d" * 64,
        max_steps=120,
        checkpoint_every=20,
        precision="bf16",
        output_dir="/workspace/checkpoints",
    )


def test_execution_maps_authorized_limits_to_training_job() -> None:
    execution = _execution()
    job = execution_to_training_job(execution)
    assert job.job_id == execution.job_id
    assert job.model_version == execution.model_version
    assert job.accelerator == execution.accelerator
    assert job.manifest_sha256 == execution.dataset_manifest_sha256
    assert job.config.max_steps == execution.max_steps
    assert job.config.checkpoint_every == execution.checkpoint_every


def test_bridge_rejects_invalid_execution() -> None:
    execution = GpuTrainingExecution(
        job_id="face-job-bridge-001",
        model_version="seldrune-face-v0.1",
        accelerator="rtx-pro-6000-blackwell",
        dataset_manifest_sha256="bad",
        max_steps=120,
        checkpoint_every=20,
        precision="bf16",
        output_dir="/workspace/checkpoints",
    )
    with pytest.raises(ValueError):
        execution_to_training_job(execution)
