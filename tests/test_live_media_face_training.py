import pytest

from services.live_media.face_training import (
    ExportFormat,
    FaceModelArtifact,
    FaceTrainingConfig,
    Precision,
    default_training_config,
)


def test_default_training_config_targets_rtx_pro_6000() -> None:
    config = default_training_config()
    assert config.accelerator == "rtx-pro-6000-blackwell"
    assert config.precision is Precision.BF16


def test_training_config_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError, match="input_size"):
        FaceTrainingConfig(input_size=250).validate()


def test_export_artifact_requires_reproducible_hashes() -> None:
    artifact = FaceModelArtifact(
        model_version="seldrune-face-v0.1",
        checkpoint_sha256="a" * 64,
        dataset_manifest_sha256="b" * 64,
        export_format=ExportFormat.ONNX,
        input_size=256,
        identity_conditioned=True,
        weights_uri="artifacts/seldrune-face-v0.1/model.onnx",
    )
    artifact.validate()


def test_export_artifact_rejects_invalid_hash() -> None:
    artifact = FaceModelArtifact(
        model_version="seldrune-face-v0.1",
        checkpoint_sha256="not-a-hash",
        dataset_manifest_sha256="b" * 64,
        export_format=ExportFormat.ONNX,
        input_size=256,
        identity_conditioned=True,
        weights_uri="model.onnx",
    )
    with pytest.raises(ValueError, match="checkpoint_sha256"):
        artifact.validate()
