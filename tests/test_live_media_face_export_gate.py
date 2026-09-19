"""Tests for Face ONNX export gating."""
from datetime import UTC, datetime

from services.live_media.face_export_gate import require_exportable_training
from services.live_media.face_gpu_receipt import GpuExecutionState, GpuTrainingReceipt


def test_success_receipt_releases_checkpoint() -> None:
    now = datetime.now(UTC)
    receipt = GpuTrainingReceipt(
        "job", "a" * 64, "seldrune-face-v0.1", "gpu", "b" * 64,
        now, now, 1, ("c" * 64,), GpuExecutionState.SUCCEEDED,
    )
    assert require_exportable_training(receipt) == "c" * 64
