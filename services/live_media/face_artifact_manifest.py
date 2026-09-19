"""Evidence manifest joining trained checkpoints and exported Face artifacts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaceArtifactManifest:
    model_version: str
    dataset_manifest_sha256: str
    checkpoint_sha256: str
    onnx_sha256: str

    def validate(self) -> None:
        if not self.model_version.startswith("seldrune-face-"):
            raise ValueError("invalid Seldrune Face model version")
        for digest in (
            self.dataset_manifest_sha256,
            self.checkpoint_sha256,
            self.onnx_sha256,
        ):
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
                raise ValueError("artifact evidence requires SHA-256 digests")
