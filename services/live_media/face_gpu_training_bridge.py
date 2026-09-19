"""Bridge admitted GPU executions into the Seldrune Face training loop."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_training import FaceTrainingConfig
from services.live_media.face_training_loop import TrainingLoopResult, run_training_loop
from services.live_media.face_training_runner import FaceTrainingJob


def execution_to_training_job(execution: GpuTrainingExecution) -> FaceTrainingJob:
    execution.validate()
    config = FaceTrainingConfig(
        model_version=execution.model_version,
        max_steps=execution.max_steps,
        checkpoint_every=execution.checkpoint_every,
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
    """Execute only the limits encoded in the admitted GPU manifest."""
    if device != "cuda":
        raise ValueError("GPU worker training requires CUDA")
    job = execution_to_training_job(execution)
    output_dir = Path(execution.output_dir)
    return run_training_loop(
        model,
        optimizer,
        batches,
        job,
        device=device,
        output_dir=output_dir,
    )
