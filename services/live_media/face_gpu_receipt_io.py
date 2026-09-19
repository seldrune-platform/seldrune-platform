"""Durable JSON evidence writer for Face GPU training receipts."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from services.live_media.face_gpu_receipt import GpuTrainingReceipt


def write_gpu_training_receipt(receipt: GpuTrainingReceipt, path: str | Path) -> Path:
    receipt.validate()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(receipt)
    payload["started_at"] = receipt.started_at.isoformat()
    payload["completed_at"] = receipt.completed_at.isoformat()
    payload["state"] = receipt.state.value
    payload["checkpoint_sha256"] = list(receipt.checkpoint_sha256)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target
