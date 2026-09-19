"""Release gate for checkpoint-backed Seldrune Face artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from services.live_media.face_training_executor import sha256_file

@dataclass(frozen=True)
class CheckpointEvidence:
    path: Path
    sha256: str

def verify_checkpoint_evidence(path: str | Path, expected_sha256: str) -> CheckpointEvidence:
    target=Path(path)
    if not target.is_file():
        raise ValueError("checkpoint file is missing")
    actual=sha256_file(target)
    if actual != expected_sha256:
        raise ValueError("checkpoint SHA-256 mismatch")
    return CheckpointEvidence(path=target, sha256=actual)
