"""Training and export contract for the Seldrune-owned Face v0.1 model."""
from dataclasses import dataclass
from enum import StrEnum


class Precision(StrEnum):
    FP32 = "fp32"
    BF16 = "bf16"
    FP16 = "fp16"


class ExportFormat(StrEnum):
    ONNX = "onnx"
    TORCHSCRIPT = "torchscript"


@dataclass(frozen=True)
class FaceTrainingConfig:
    model_version: str = "seldrune-face-v0.1"
    accelerator: str = "rtx-pro-6000-blackwell"
    input_size: int = 256
    batch_size: int = 16
    learning_rate: float = 0.0001
    precision: Precision = Precision.BF16
    max_steps: int = 100_000
    checkpoint_every: int = 2_000

    def validate(self) -> None:
        if self.input_size < 128 or self.input_size % 32:
            raise ValueError("input_size must be >=128 and divisible by 32")
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive")
        if not 0 < self.learning_rate < 1:
            raise ValueError("learning_rate must be between 0 and 1")
        if self.max_steps < 1 or self.checkpoint_every < 1:
            raise ValueError("training steps must be positive")
        if self.checkpoint_every > self.max_steps:
            raise ValueError("checkpoint interval cannot exceed max_steps")


@dataclass(frozen=True)
class FaceModelArtifact:
    model_version: str
    checkpoint_sha256: str
    dataset_manifest_sha256: str
    export_format: ExportFormat
    input_size: int
    identity_conditioned: bool
    weights_uri: str

    def validate(self) -> None:
        if not self.model_version.startswith("seldrune-face-"):
            raise ValueError("artifact must be a Seldrune Face model")
        for name, digest in (
            ("checkpoint_sha256", self.checkpoint_sha256),
            ("dataset_manifest_sha256", self.dataset_manifest_sha256),
        ):
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
                raise ValueError(f"{name} must be a SHA-256 digest")
        if self.input_size < 128 or self.input_size % 32:
            raise ValueError("artifact input_size is invalid")
        if not self.identity_conditioned:
            raise ValueError("Face v0.1 export must be identity-conditioned")
        if not self.weights_uri.strip():
            raise ValueError("weights_uri is required")


def default_training_config() -> FaceTrainingConfig:
    config = FaceTrainingConfig()
    config.validate()
    return config
