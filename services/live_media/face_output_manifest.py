"""Manifest for verifiable Face v0.1 outputs."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FaceOutputManifest:
    model_version: str
    checkpoint_sha256: str
    dataset_manifest_sha256: str
    onnx_sha256: str | None=None
    def validate(self) -> None:
        if not self.model_version.startswith("seldrune-face-"):
            raise ValueError("invalid model version")
        for digest in (self.checkpoint_sha256,self.dataset_manifest_sha256):
            if len(digest)!=64:
                raise ValueError("SHA-256 evidence required")
        if self.onnx_sha256 is not None and len(self.onnx_sha256)!=64:
            raise ValueError("invalid ONNX SHA-256")
