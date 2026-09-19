from pathlib import Path
from unittest.mock import patch

import pytest

from services.live_media.face_onnx_export import OnnxExportArtifact, export_face_model_onnx


class _Model:
    def to(self, device):
        return self

    def eval(self):
        return self


class _Torch:
    @staticmethod
    def zeros(*args, **kwargs):
        return object()

    class onnx:
        @staticmethod
        def export(model, inputs, path, **kwargs):
            Path(path).write_bytes(b"seldrune-onnx-test")


def test_export_writes_hashed_artifact(tmp_path):
    path = tmp_path / "face.onnx"
    with patch.dict("sys.modules", {"torch": _Torch}):
        artifact = export_face_model_onnx(_Model(), output_path=path)

    assert path.exists()
    assert len(artifact.sha256) == 64
    assert artifact.input_size == 256
    assert artifact.identity_embedding_dim == 512
    assert artifact.opset_version == 17


@pytest.mark.parametrize(
    ("field", "value"),
    [("input_size", 127), ("identity_embedding_dim", 64), ("opset_version", 16)],
)
def test_artifact_rejects_invalid_contract(field, value):
    values = {
        "path": "face.onnx",
        "sha256": "a" * 64,
        "input_size": 256,
        "identity_embedding_dim": 512,
        "opset_version": 17,
    }
    values[field] = value
    with pytest.raises(ValueError):
        OnnxExportArtifact(**values).validate()


def test_artifact_rejects_invalid_digest():
    with pytest.raises(ValueError, match="SHA-256"):
        OnnxExportArtifact(
            path="face.onnx",
            sha256="bad",
            input_size=256,
            identity_embedding_dim=512,
            opset_version=17,
        ).validate()
