"""Training execution contracts for Seldrune Face v0.1."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .face_training_runner import FaceTrainingJob


@dataclass(frozen=True)
class TrainingCheckpoint:
    job_id: str
    step: int
    path: str
    sha256: str
    manifest_sha256: str

    def validate(self) -> None:
        if self.step < 1:
            raise ValueError("checkpoint step must be positive")
        if len(self.sha256) != 64 or len(self.manifest_sha256) != 64:
            raise ValueError("checkpoint evidence requires SHA-256 digests")


class TrainingExecutor(Protocol):
    def train(self, job: FaceTrainingJob) -> TrainingCheckpoint: ...


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checkpoint(checkpoint: TrainingCheckpoint) -> bool:
    checkpoint.validate()
    path = Path(checkpoint.path)
    return path.is_file() and sha256_file(path) == checkpoint.sha256
