"""Worker integration test for the paired source/reference Face v0.1 path."""
from types import SimpleNamespace
from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_worker import run_training

def test_run_training_uses_paired_bridge(monkeypatch) -> None:
    execution=GpuTrainingExecution(job_id="face-job-worker-001",model_version="seldrune-face-v0.1",
        accelerator="rtx-pro-6000-blackwell",dataset_manifest_sha256="e"*64,max_steps=2,
        checkpoint_every=1,precision="bf16",output_dir="/tmp/seldrune-face")
    result=SimpleNamespace(completed_steps=2,last_loss=.2,device="cuda",
        checkpoints=(SimpleNamespace(sha256="f"*64),))
    monkeypatch.setattr("services.live_media.face_gpu_worker.execute_admitted_paired_training",lambda *args,**kwargs:result)
    payload=run_training(execution,object(),object(),[object()])
    assert payload["status"]=="trained"
    assert payload["completed_steps"]==2
    assert payload["checkpoint_sha256"]==["f"*64]
