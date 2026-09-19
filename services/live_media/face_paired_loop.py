"""Bounded paired-training loop for Seldrune Face v0.1."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .face_paired_training import PairedTrainingBatch, paired_train_step


@dataclass(frozen=True)
class PairedLoopResult:
    completed_steps: int
    last_loss: float


def run_paired_loop(
    model: Any,
    optimizer: Any,
    batches: Sequence[PairedTrainingBatch],
    *,
    device: str,
    max_steps: int,
) -> PairedLoopResult:
    if not batches or max_steps < 1:
        raise ValueError("paired training requires batches and positive steps")
    loss = 0.0
    for step in range(max_steps):
        loss = paired_train_step(model, batches[step % len(batches)], optimizer, device=device)
    return PairedLoopResult(max_steps, loss)
