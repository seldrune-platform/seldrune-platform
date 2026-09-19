"""Compact evidence summary for Owner Console telemetry."""
from __future__ import annotations
from dataclasses import asdict
from services.live_media.face_gpu_receipt import GpuTrainingReceipt

def receipt_summary(receipt: GpuTrainingReceipt) -> dict[str, object]:
    receipt.validate()
    return {
        "job_id":receipt.job_id,
        "model_version":receipt.model_version,
        "state":receipt.state.value,
        "final_step":receipt.final_step,
        "checkpoint_count":len(receipt.checkpoint_sha256),
        "completed_at":receipt.completed_at.isoformat(),
    }
