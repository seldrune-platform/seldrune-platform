"""Tests binding Face GPU executions to worker receipts."""
from datetime import UTC, datetime

import pytest

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_receipt import GpuExecutionState, GpuTrainingReceipt
from services.live_media.face_gpu_worker_binding import (
    GpuWorkerIdentity,
    verify_execution_receipt,
)


def _execution() -> GpuTrainingExecution:
    return GpuTrainingExecution(
        job_id="face-job-001",
        model_version="seldrune-face-v0.1",
        accelerator="rtx-pro-6000-blackwell",
        dataset_manifest_sha256="b" * 64,
        max_steps=100,
        checkpoint_every=10,
        precision="bf16",
        output_dir="/workspace/checkpoints",
    )


def _receipt(execution: GpuTrainingExecution, **overrides: object) -> GpuTrainingReceipt:
    now = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)
    values = {
        "job_id": execution.job_id,
        "execution_digest": execution.digest(),
        "model_version": execution.model_version,
        "accelerator": execution.accelerator,
        "dataset_manifest_sha256": execution.dataset_manifest_sha256,
        "started_at": now,
        "completed_at": now,
        "final_step": 100,
        "checkpoint_sha256": ("c" * 64,),
        "state": GpuExecutionState.SUCCEEDED,
        "error": None,
    }
    values.update(overrides)
    return GpuTrainingReceipt(**values)


def _worker(**overrides: object) -> GpuWorkerIdentity:
    values = {
        "worker_id": "runpod-rtx-pro-6000-01",
        "accelerator": "rtx-pro-6000-blackwell",
        "cuda_available": True,
    }
    values.update(overrides)
    return GpuWorkerIdentity(**values)


def test_matching_execution_receipt_is_verified() -> None:
    execution = _execution()
    verify_execution_receipt(execution, _receipt(execution), _worker())


def test_wrong_execution_digest_is_rejected() -> None:
    execution = _execution()
    with pytest.raises(ValueError):
        verify_execution_receipt(
            execution,
            _receipt(execution, execution_digest="a" * 64),
            _worker(),
        )


def test_wrong_worker_accelerator_is_rejected() -> None:
    execution = _execution()
    with pytest.raises(ValueError):
        verify_execution_receipt(
            execution,
            _receipt(execution),
            _worker(accelerator="other-gpu"),
        )


def test_non_cuda_worker_is_rejected() -> None:
    execution = _execution()
    with pytest.raises(ValueError):
        verify_execution_receipt(
            execution,
            _receipt(execution),
            _worker(cuda_available=False),
        )


def test_receipt_cannot_exceed_admitted_step_budget() -> None:
    execution = _execution()
    with pytest.raises(ValueError):
        verify_execution_receipt(
            execution,
            _receipt(execution, final_step=101),
            _worker(),
        )
