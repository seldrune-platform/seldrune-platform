"""Verifiable receipt contract for Seldrune Face GPU training execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class GpuExecutionState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class GpuTrainingReceipt:
    job_id: str
    execution_digest: str
    model_version: str
    accelerator: str
    dataset_manifest_sha256: str
    started_at: datetime
    completed_at: datetime
    final_step: int
    checkpoint_sha256: tuple[str, ...]
    state: GpuExecutionState
    error: str | None = None

    def validate(self) -> None:
        if not self.job_id or not self.model_version.startswith("seldrune-face-"):
            raise ValueError("invalid job/model identity")
        for digest in (
            self.execution_digest,
            self.dataset_manifest_sha256,
            *self.checkpoint_sha256,
        ):
            if len(digest) != 64:
                raise ValueError("receipt digests must be SHA-256")
        if self.completed_at < self.started_at:
            raise ValueError("completion cannot precede start")
        if self.final_step < 0:
            raise ValueError("final_step cannot be negative")
        if self.state is GpuExecutionState.SUCCEEDED:
            if self.final_step < 1 or not self.checkpoint_sha256:
                raise ValueError("successful execution requires checkpoint evidence")
            if self.error:
                raise ValueError("successful execution cannot contain an error")
        elif not self.error:
            raise ValueError("failed execution requires an error")
