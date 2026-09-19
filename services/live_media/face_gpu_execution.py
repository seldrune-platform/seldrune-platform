"""Portable execution manifest for Seldrune Face v0.1 GPU training."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path

from .face_training_runner import FaceTrainingJob


@dataclass(frozen=True)
class GpuTrainingExecution:
    job_id: str
    model_version: str
    accelerator: str
    dataset_manifest_sha256: str
    max_steps: int
    checkpoint_every: int
    precision: str
    output_dir: str

    def validate(self) -> None:
        if not self.job_id or not self.model_version.startswith("seldrune-face-"):
            raise ValueError("invalid Seldrune Face training identity")
        if len(self.dataset_manifest_sha256) != 64:
            raise ValueError("dataset manifest requires SHA-256")
        if self.max_steps < 1 or self.checkpoint_every < 1:
            raise ValueError("training bounds must be positive")
        if self.checkpoint_every > self.max_steps:
            raise ValueError("checkpoint interval exceeds max steps")
        if not self.output_dir:
            raise ValueError("output directory is required")

    def digest(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()


def build_gpu_execution(
    job: FaceTrainingJob,
    *,
    output_dir: str | Path,
) -> GpuTrainingExecution:
    execution = GpuTrainingExecution(
        job_id=job.job_id,
        model_version=job.model_version,
        accelerator=job.accelerator,
        dataset_manifest_sha256=job.manifest_sha256,
        max_steps=job.config.max_steps,
        checkpoint_every=job.config.checkpoint_every,
        precision=job.config.precision.value,
        output_dir=str(output_dir),
    )
    execution.validate()
    return execution


def write_gpu_execution_manifest(
    execution: GpuTrainingExecution,
    path: str | Path,
) -> str:
    execution.validate()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(execution), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return execution.digest()
