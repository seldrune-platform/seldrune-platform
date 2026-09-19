"""Tests for the Face GPU training coordinator without requiring CUDA."""
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from services.live_media.face_gpu_coordinator import coordinate_gpu_training
from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_receipt import GpuExecutionState
from services.live_media.face_training_executor import TrainingCheckpoint


def _execution() -> GpuTrainingExecution:
    return GpuTrainingExecution(
        job_id="face-job-001",
        model_version="seldrune-face-v0.1",
        accelerator="rtx-pro-6000-blackwell",
        dataset_manifest_sha256="a" * 64,
        max_steps=2,
        checkpoint_every=1,
        precision="bf16",
        output_dir="/tmp/seldrune-face",
    )


def test_coordinate_gpu_training_emits_checkpoint_backed_receipt(monkeypatch) -> None:
    execution = _execution()
    runtime = SimpleNamespace(model=object(), optimizer=object(), device="cuda")
    checkpoint = TrainingCheckpoint(
        job_id=execution.job_id,
        step=1,
        path="/tmp/checkpoint.pt",
        sha256="b" * 64,
        manifest_sha256=execution.dataset_manifest_sha256,
    )
    result = SimpleNamespace(
        completed_steps=1,
        last_loss=0.25,
        device="cuda",
        checkpoints=(checkpoint,),
    )

    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.build_gpu_runtime",
        lambda value: runtime,
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.build_tensor_batches",
        lambda samples, batch_size: [("image", "identity", "target")],
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.execute_admitted_training",
        lambda *args, **kwargs: result,
    )

    coordinated = coordinate_gpu_training(execution, [object()], batch_size=1)

    assert coordinated.last_loss == 0.25
    assert coordinated.receipt.state is GpuExecutionState.SUCCEEDED
    assert coordinated.receipt.final_step == 1
    assert coordinated.receipt.checkpoint_sha256 == ("b" * 64,)
    assert coordinated.receipt.execution_digest == execution.digest()


def test_coordinate_gpu_training_rejects_success_without_checkpoint(monkeypatch) -> None:
    execution = _execution()
    runtime = SimpleNamespace(model=object(), optimizer=object(), device="cuda")
    result = SimpleNamespace(
        completed_steps=1,
        last_loss=0.25,
        device="cuda",
        checkpoints=(),
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.build_gpu_runtime",
        lambda value: runtime,
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.build_tensor_batches",
        lambda samples, batch_size: [("image", "identity", "target")],
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.execute_admitted_training",
        lambda *args, **kwargs: result,
    )

    with pytest.raises(ValueError, match="checkpoint evidence"):
        coordinate_gpu_training(execution, [object()], batch_size=1)


def test_receipt_timestamps_are_timezone_aware(monkeypatch) -> None:
    execution = _execution()
    runtime = SimpleNamespace(model=object(), optimizer=object(), device="cuda")
    checkpoint = TrainingCheckpoint(
        job_id=execution.job_id,
        step=1,
        path="/tmp/checkpoint.pt",
        sha256="c" * 64,
        manifest_sha256=execution.dataset_manifest_sha256,
    )
    result = SimpleNamespace(
        completed_steps=1,
        last_loss=0.1,
        device="cuda",
        checkpoints=(checkpoint,),
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.build_gpu_runtime",
        lambda value: runtime,
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.build_tensor_batches",
        lambda samples, batch_size: [("image", "identity", "target")],
    )
    monkeypatch.setattr(
        "services.live_media.face_gpu_coordinator.execute_admitted_training",
        lambda *args, **kwargs: result,
    )

    receipt = coordinate_gpu_training(execution, [object()], batch_size=1).receipt

    assert receipt.started_at.tzinfo is UTC
    assert receipt.completed_at.tzinfo is UTC
    assert isinstance(receipt.started_at, datetime)
