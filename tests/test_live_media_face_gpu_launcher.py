"""Tests for provider-neutral Face GPU worker launch contracts."""
import pytest

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_launcher import (
    GpuLaunchHandle,
    GpuLaunchRequest,
    build_face_training_launch,
)
from services.live_media.face_gpu_worker_binding import GpuWorkerIdentity


def _execution() -> GpuTrainingExecution:
    return GpuTrainingExecution(
        job_id="face-job-001",
        model_version="seldrune-face-v0.1",
        accelerator="rtx-pro-6000-blackwell",
        dataset_manifest_sha256="a" * 64,
        max_steps=100,
        checkpoint_every=10,
        precision="bf16",
        output_dir="/workspace/checkpoints",
    )


def _worker(accelerator: str = "rtx-pro-6000-blackwell") -> GpuWorkerIdentity:
    return GpuWorkerIdentity(
        worker_id="gpu-worker-01",
        accelerator=accelerator,
        cuda_available=True,
    )


def test_build_launch_for_matching_worker() -> None:
    request = build_face_training_launch(_execution(), _worker())
    request.validate()
    assert request.command[-1] == "execution.json"
    assert request.environment_keys == ("SELDRUNE_GPU_WORKER_ID",)


def test_launch_rejects_wrong_accelerator() -> None:
    with pytest.raises(ValueError):
        build_face_training_launch(_execution(), _worker("other-gpu"))


def test_launch_rejects_empty_command() -> None:
    request = GpuLaunchRequest(
        execution=_execution(),
        worker=_worker(),
        command=(),
    )
    with pytest.raises(ValueError):
        request.validate()


def test_launch_rejects_duplicate_environment_keys() -> None:
    request = GpuLaunchRequest(
        execution=_execution(),
        worker=_worker(),
        command=("python",),
        environment_keys=("A", "A"),
    )
    with pytest.raises(ValueError):
        request.validate()


def test_launch_handle_requires_remote_identity() -> None:
    with pytest.raises(ValueError):
        GpuLaunchHandle(
            provider="runpod",
            worker_id="gpu-worker-01",
            remote_run_id="",
        ).validate()
