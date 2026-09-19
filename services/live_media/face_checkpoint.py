"""Checkpoint writer for Seldrune Face v0.1 PyTorch training."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .face_training_executor import TrainingCheckpoint, sha256_file
from .face_training_runner import FaceTrainingJob


def write_checkpoint(
    model: Any,
    optimizer: Any,
    job: FaceTrainingJob,
    *,
    step: int,
    output_dir: str | Path,
) -> TrainingCheckpoint:
    if step < 1:
        raise ValueError("checkpoint step must be positive")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to write a training checkpoint") from exc

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{job.model_version}-step-{step}.pt"
    torch.save(
        {
            "model_version": job.model_version,
            "job_id": job.job_id,
            "step": step,
            "manifest_sha256": job.manifest_sha256,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        path,
    )
    checkpoint = TrainingCheckpoint(
        job_id=job.job_id,
        step=step,
        path=str(path),
        sha256=sha256_file(path),
        manifest_sha256=job.manifest_sha256,
    )
    checkpoint.validate()
    return checkpoint
