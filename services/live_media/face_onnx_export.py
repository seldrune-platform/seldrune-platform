"""ONNX exporters for Seldrune Face v0.1."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OnnxExportArtifact:
    path: str
    sha256: str
    input_size: int
    identity_embedding_dim: int
    opset_version: int
    conditioning: str = "identity_embedding"

    def validate(self) -> None:
        if len(self.sha256) != 64:
            raise ValueError("ONNX artifact requires a SHA-256 digest")
        if self.input_size < 128 or self.input_size % 32:
            raise ValueError("input_size must be >=128 and divisible by 32")
        if self.identity_embedding_dim < 128:
            raise ValueError("identity embedding dimension is too small")
        if self.opset_version < 17:
            raise ValueError("ONNX opset must be 17 or newer")
        if self.conditioning not in {"identity_embedding", "reference_image"}:
            raise ValueError("unsupported Face conditioning mode")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_export_args(input_size: int, identity_embedding_dim: int, opset_version: int) -> None:
    if input_size < 128 or input_size % 32:
        raise ValueError("input_size must be >=128 and divisible by 32")
    if identity_embedding_dim < 128:
        raise ValueError("identity embedding dimension is too small")
    if opset_version < 17:
        raise ValueError("ONNX opset must be 17 or newer")


def export_face_model_onnx(
    model: Any,
    *,
    output_path: str | Path,
    input_size: int = 256,
    identity_embedding_dim: int = 512,
    opset_version: int = 17,
    device: str = "cpu",
) -> OnnxExportArtifact:
    """Export the legacy embedding-conditioned Face model."""
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for ONNX export") from exc
    _validate_export_args(input_size, identity_embedding_dim, opset_version)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    model = model.to(device)
    model.eval()
    image = torch.zeros(1, 3, input_size, input_size, device=device)
    identity = torch.zeros(1, identity_embedding_dim, device=device)
    torch.onnx.export(
        model, (image, identity), path,
        input_names=["image", "identity_embedding"],
        output_names=["transformed_image"],
        dynamic_axes={
            "image": {0: "batch"},
            "identity_embedding": {0: "batch"},
            "transformed_image": {0: "batch"},
        },
        opset_version=opset_version,
        do_constant_folding=True,
    )
    artifact = OnnxExportArtifact(
        path=str(path), sha256=_sha256_file(path), input_size=input_size,
        identity_embedding_dim=identity_embedding_dim, opset_version=opset_version,
    )
    artifact.validate()
    return artifact


def export_reference_conditioned_face_onnx(
    model: Any,
    *,
    output_path: str | Path,
    input_size: int = 256,
    identity_embedding_dim: int = 512,
    opset_version: int = 17,
    device: str = "cpu",
) -> OnnxExportArtifact:
    """Export the trained source/reference-image conditioned Face v0.1 model."""
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for ONNX export") from exc
    _validate_export_args(input_size, identity_embedding_dim, opset_version)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    model = model.to(device)
    model.eval()
    source = torch.zeros(1, 3, input_size, input_size, device=device)
    reference = torch.zeros(1, 3, input_size, input_size, device=device)
    torch.onnx.export(
        model, (source, reference), path,
        input_names=["source_image", "reference_image"],
        output_names=["transformed_image"],
        dynamic_axes={
            "source_image": {0: "batch"},
            "reference_image": {0: "batch"},
            "transformed_image": {0: "batch"},
        },
        opset_version=opset_version,
        do_constant_folding=True,
    )
    artifact = OnnxExportArtifact(
        path=str(path), sha256=_sha256_file(path), input_size=input_size,
        identity_embedding_dim=identity_embedding_dim, opset_version=opset_version,
        conditioning="reference_image",
    )
    artifact.validate()
    return artifact
