"""Tests for durable Face GPU receipt evidence."""
from datetime import UTC, datetime
import json

from services.live_media.face_gpu_receipt import GpuExecutionState, GpuTrainingReceipt
from services.live_media.face_gpu_receipt_io import write_gpu_training_receipt


def test_write_receipt(tmp_path) -> None:
    now = datetime.now(UTC)
    receipt = GpuTrainingReceipt(
        job_id="job-1",
        execution_digest="a" * 64,
        model_version="seldrune-face-v0.1",
        accelerator="rtx-pro-6000-blackwell",
        dataset_manifest_sha256="b" * 64,
        started_at=now,
        completed_at=now,
        final_step=1,
        checkpoint_sha256=("c" * 64,),
        state=GpuExecutionState.SUCCEEDED,
    )
    path = write_gpu_training_receipt(receipt, tmp_path / "receipt.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["state"] == "succeeded"
    assert payload["checkpoint_sha256"] == ["c" * 64]
