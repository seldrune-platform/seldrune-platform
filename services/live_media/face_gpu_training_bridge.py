"""Bridge admitted GPU executions into Seldrune Face training loops."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from services.live_media.face_checkpoint import write_checkpoint
from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_paired_training import PairedTrainingBatch, paired_train_step
from services.live_media.face_training import FaceTrainingConfig, Precision
from services.live_media.face_training_loop import TrainingLoopResult, run_training_loop
from services.live_media.face_training_runner import FaceTrainingJob


def execution_to_training_job(execution: GpuTrainingExecution) -> FaceTrainingJob:
    execution.validate()
    config = FaceTrainingConfig(
        model_version=execution.model_version,
        max_steps=execution.max_steps,
        checkpoint_every=execution.checkpoint_every,
        precision=Precision(execution.precision),
    )
    config.validate()
    return FaceTrainingJob(
        job_id=execution.job_id,
        model_version=execution.model_version,
        accelerator=execution.accelerator,
        manifest_sha256=execution.dataset_manifest_sha256,
        subject_count=0,
        capture_count=0,
        config=config,
    )


def execute_admitted_training(
    execution: GpuTrainingExecution,
    model: Any,
    optimizer: Any,
    batches: Iterable[tuple[Any, Any, Any]],
    *,
    device: str = "cuda",
) -> TrainingLoopResult:
    """Legacy embedding-conditioned loop retained for checkpoint compatibility."""
    if device != "cuda":
        raise ValueError("GPU worker training requires CUDA")
    job = execution_to_training_job(execution)
    return run_training_loop(
        model,
        optimizer,
        batches,
        job,
        device=device,
        output_dir=Path(execution.output_dir),
    )


def execute_admitted_paired_training(
    execution: GpuTrainingExecution,
    model: Any,
    optimizer: Any,
    batches: Iterable[PairedTrainingBatch],
    *,
    device: str = "cuda",
) -> TrainingLoopResult:
    """Train source/reference pairs within the exact admitted execution limits."""
    if device != "cuda":
        raise ValueError("GPU worker training requires CUDA")
    job = execution_to_training_job(execution)
    checkpoints = []
    last = None
    completed = 0
    for batch in batches:
        if completed >= job.config.max_steps:
            break
        completed += 1
        last = paired_train_step(
            model,
            batch,
            optimizer,
            device=device,
            precision=execution.precision,
        )
        if completed % job.config.checkpoint_every == 0 or completed == job.config.max_steps:
            checkpoints.append(
                write_checkpoint(
                    model,
                    optimizer,
                    job,
                    step=completed,
                    output_dir=Path(execution.output_dir),
                )
            )
    if last is None:
        raise ValueError("paired training requires at least one admitted batch")
    return TrainingLoopResult(
        completed_steps=completed,
        last_loss=last.loss,
        device=last.device,
        checkpoints=tuple(checkpoints),
    )
