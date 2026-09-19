"""CUDA runtime for reference-conditioned Seldrune Face training."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .face_architecture import default_face_architecture
from .face_gpu_execution import GpuTrainingExecution
from .face_reference_model import build_reference_conditioned_model


@dataclass(frozen=True)
class PairedFaceGpuRuntime:
    model: Any
    optimizer: Any
    device: str


def build_paired_gpu_runtime(
    execution: GpuTrainingExecution,
    *,
    learning_rate: float = 0.0001,
) -> PairedFaceGpuRuntime:
    execution.validate()
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for paired Face training") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for paired Face training")
    model = build_reference_conditioned_model(default_face_architecture()).to("cuda")
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    return PairedFaceGpuRuntime(model, optimizer, "cuda")
