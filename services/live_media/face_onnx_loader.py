"""ONNX Runtime loader for Seldrune Face v0.1 LiveShift inference."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoadedFaceModel:
    path: str
    sha256: str
    providers: tuple[str, ...]
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load_face_onnx(
    artifact_path: str | Path,
    *,
    expected_sha256: str,
    prefer_cuda: bool = True,
) -> tuple[Any, LoadedFaceModel]:
    """Verify and load a Seldrune-owned ONNX artifact for LiveShift."""
    path = Path(artifact_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = _digest(path)
    if len(expected_sha256) != 64 or actual != expected_sha256:
        raise ValueError("Face model artifact SHA-256 verification failed")

    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("ONNX Runtime is required for LiveShift face inference") from exc

    available = tuple(ort.get_available_providers())
    providers: list[str] = []
    if prefer_cuda and "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    if "CPUExecutionProvider" in available:
        providers.append("CPUExecutionProvider")
    if not providers:
        raise RuntimeError("No supported ONNX Runtime execution provider is available")

    session = ort.InferenceSession(str(path), providers=providers)
    inputs = tuple(item.name for item in session.get_inputs())
    outputs = tuple(item.name for item in session.get_outputs())
    required = {"image", "identity_embedding"}
    if not required.issubset(inputs):
        raise ValueError("Face model ONNX inputs do not match the LiveShift contract")
    if "transformed_image" not in outputs:
        raise ValueError("Face model ONNX output does not match the LiveShift contract")

    loaded = LoadedFaceModel(
        path=str(path),
        sha256=actual,
        providers=tuple(session.get_providers()),
        input_names=inputs,
        output_names=outputs,
    )
    return session, loaded
