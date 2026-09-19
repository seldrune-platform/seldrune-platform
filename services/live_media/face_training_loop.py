"""Bounded multi-step training loop for Seldrune Face v0.1."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .face_checkpoint import write_checkpoint
from .face_torch_training import TrainingStepResult, train_step
from .face_training_executor import TrainingCheckpoint
from .face_training_runner import FaceTrainingJob


@dataclass(frozen=True)
class TrainingLoopResult:
    completed_steps: int
    last_loss: float
    device: str
    checkpoints: tuple[TrainingCheckpoint, ...]


def run_training_loop(
    model: Any,
    optimizer: Any,
    batches: Iterable[tuple[Any, Any, Any]],
    job: FaceTrainingJob,
    *,
    device: str,
    output_dir: str | Path,
    start_step: int = 0,
) -> TrainingLoopResult:
    """Train admitted batches up to the configured bound and checkpoint periodically."""
    if start_step < 0 or start_step >= job.config.max_steps:
        raise ValueError("start_step must be within the configured training range")

    checkpoints: list[TrainingCheckpoint] = []
    last: TrainingStepResult | None = None
    step = start_step
    for image, identity_embedding, target in batches:
        if step >= job.config.max_steps:
            break
        step += 1
        last = train_step(
            model,
            image,
            identity_embedding,
            target,
            optimizer,
            device=device,
        )
        if step % job.config.checkpoint_every == 0 or step == job.config.max_steps:
            checkpoints.append(
                write_checkpoint(
                    model,
                    optimizer,
                    job,
                    step=step,
                    output_dir=output_dir,
                )
            )

    if last is None:
        raise ValueError("training loop requires at least one admitted batch")

    return TrainingLoopResult(
        completed_steps=step - start_step,
        last_loss=last.loss,
        device=last.device,
        checkpoints=tuple(checkpoints),
    )
