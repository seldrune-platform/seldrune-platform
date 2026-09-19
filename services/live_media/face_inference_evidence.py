"""Measured inference evidence for trained Face artifacts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FaceInferenceEvidence:
    model_sha256: str
    input_sha256: str
    output_sha256: str
    inference_ms: float

    def validate(self) -> None:
        for digest in (self.model_sha256, self.input_sha256, self.output_sha256):
            if len(digest) != 64:
                raise ValueError("inference evidence requires SHA-256 digests")
        if self.input_sha256 == self.output_sha256:
            raise ValueError("output evidence must differ from input")
        if self.inference_ms <= 0:
            raise ValueError("inference latency must be positive")
