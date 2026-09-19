from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.live_media.face_onnx_loader import load_face_onnx


class _Session:
    def __init__(self, path, providers):
        self.providers = providers

    def get_inputs(self):
        return [SimpleNamespace(name="image"), SimpleNamespace(name="identity_embedding")]

    def get_outputs(self):
        return [SimpleNamespace(name="transformed_image")]

    def get_providers(self):
        return self.providers


class _Ort:
    InferenceSession = _Session

    @staticmethod
    def get_available_providers():
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_loader_verifies_artifact_and_prefers_cuda(tmp_path):
    path = tmp_path / "face.onnx"
    payload = b"seldrune-face-v01"
    path.write_bytes(payload)
    expected = sha256(payload).hexdigest()

    with patch.dict("sys.modules", {"onnxruntime": _Ort}):
        session, loaded = load_face_onnx(path, expected_sha256=expected)

    assert session is not None
    assert loaded.sha256 == expected
    assert loaded.providers[0] == "CUDAExecutionProvider"
    assert loaded.input_names == ("image", "identity_embedding")
    assert loaded.output_names == ("transformed_image",)


def test_loader_rejects_digest_mismatch(tmp_path):
    path = tmp_path / "face.onnx"
    path.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="SHA-256"):
        load_face_onnx(path, expected_sha256="a" * 64)


def test_loader_rejects_missing_artifact(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_face_onnx(tmp_path / "missing.onnx", expected_sha256="a" * 64)


def test_loader_can_force_cpu_preference(tmp_path):
    path = tmp_path / "face.onnx"
    payload = b"cpu-test"
    path.write_bytes(payload)
    expected = sha256(payload).hexdigest()

    with patch.dict("sys.modules", {"onnxruntime": _Ort}):
        _, loaded = load_face_onnx(path, expected_sha256=expected, prefer_cuda=False)

    assert loaded.providers == ("CPUExecutionProvider",)


class _ReferenceSession(_Session):
    def get_inputs(self):
        return [SimpleNamespace(name="source_image"), SimpleNamespace(name="reference_image")]


class _ReferenceOrt(_Ort):
    InferenceSession = _ReferenceSession


def test_loader_accepts_reference_conditioned_contract(tmp_path):
    path = tmp_path / "face-reference.onnx"
    payload = b"seldrune-face-v01-reference"
    path.write_bytes(payload)
    expected = sha256(payload).hexdigest()

    with patch.dict("sys.modules", {"onnxruntime": _ReferenceOrt}):
        _, loaded = load_face_onnx(path, expected_sha256=expected)

    assert loaded.providers[0] == "CUDAExecutionProvider"
    assert loaded.input_names == ("source_image", "reference_image")
    assert loaded.output_names == ("transformed_image",)
