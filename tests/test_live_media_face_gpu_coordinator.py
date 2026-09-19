"""Tests for the Face GPU training coordinator without requiring CUDA."""
from datetime import UTC, datetime
from types import SimpleNamespace
import pytest
from services.live_media.face_gpu_coordinator import coordinate_gpu_training
from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_receipt import GpuExecutionState
from services.live_media.face_training_executor import TrainingCheckpoint

def _execution(*, accelerator: str = "rtx-pro-6000-blackwell") -> GpuTrainingExecution:
    return GpuTrainingExecution(job_id="face-job-001", model_version="seldrune-face-v0.1",
        accelerator=accelerator, dataset_manifest_sha256="a"*64, max_steps=2,
        checkpoint_every=1, precision="bf16", output_dir="/tmp/seldrune-face")

def _checkpoint(execution, digest="b"):
    return TrainingCheckpoint(job_id=execution.job_id, step=1, path="/tmp/checkpoint.pt",
        sha256=digest*64, manifest_sha256=execution.dataset_manifest_sha256)

def test_coordinate_gpu_training_uses_paired_reference_runtime(monkeypatch) -> None:
    execution=_execution(); runtime=SimpleNamespace(model=object(),optimizer=object(),device="cuda")
    result=SimpleNamespace(completed_steps=1,last_loss=.25,device="cuda",checkpoints=(_checkpoint(execution),))
    calls=[]
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.build_paired_gpu_runtime",lambda value:calls.append(("runtime",value.accelerator)) or runtime)
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.build_paired_batches",lambda samples,batch_size:calls.append(("pairs",batch_size)) or [object()])
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.execute_admitted_paired_training",lambda *args,**kwargs:calls.append(("train",kwargs["device"])) or result)
    coordinated=coordinate_gpu_training(execution,[object()],batch_size=4)
    assert calls==[("runtime","rtx-pro-6000-blackwell"),("pairs",4),("train","cuda")]
    assert coordinated.receipt.state is GpuExecutionState.SUCCEEDED
    assert coordinated.receipt.checkpoint_sha256==("b"*64,)

def test_coordinate_gpu_training_rejects_wrong_accelerator_before_runtime(monkeypatch) -> None:
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.build_paired_gpu_runtime",lambda value:pytest.fail("runtime must not start"))
    with pytest.raises(ValueError,match="RTX PRO 6000"):
        coordinate_gpu_training(_execution(accelerator="generic-cuda"),[object()],batch_size=1)

def test_coordinate_gpu_training_rejects_success_without_checkpoint(monkeypatch) -> None:
    execution=_execution(); runtime=SimpleNamespace(model=object(),optimizer=object(),device="cuda")
    result=SimpleNamespace(completed_steps=1,last_loss=.25,device="cuda",checkpoints=())
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.build_paired_gpu_runtime",lambda value:runtime)
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.build_paired_batches",lambda samples,batch_size:[object()])
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.execute_admitted_paired_training",lambda *args,**kwargs:result)
    with pytest.raises(ValueError,match="checkpoint evidence"):
        coordinate_gpu_training(execution,[object()],batch_size=1)

def test_receipt_timestamps_are_timezone_aware(monkeypatch) -> None:
    execution=_execution(); runtime=SimpleNamespace(model=object(),optimizer=object(),device="cuda")
    result=SimpleNamespace(completed_steps=1,last_loss=.1,device="cuda",checkpoints=(_checkpoint(execution,"c"),))
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.build_paired_gpu_runtime",lambda value:runtime)
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.build_paired_batches",lambda samples,batch_size:[object()])
    monkeypatch.setattr("services.live_media.face_gpu_coordinator.execute_admitted_paired_training",lambda *args,**kwargs:result)
    receipt=coordinate_gpu_training(execution,[object()],batch_size=1).receipt
    assert receipt.started_at.tzinfo is UTC and receipt.completed_at.tzinfo is UTC
    assert isinstance(receipt.started_at,datetime)
