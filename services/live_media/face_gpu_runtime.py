"""Runtime construction for admitted Seldrune Face GPU training."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.live_media.face_architecture import default_face_architecture
from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_reference_model import build_reference_conditioned_model


@dataclass(frozen=True)
class FaceGpuRuntime:
    model: Any
    optimizer: Any
    device: str
    learning_rate: float


def build_gpu_runtime(
    execution: GpuTrainingExecution,
    *,
    learning_rate: float = 0.0001,
) -> FaceGpuRuntime:
    """Construct the untrained Seldrune reference-conditioned model on CUDA."""
    execution.validate()
    if not 0 < learning_rate < 1:
        raise ValueError("learning_rate must be between 0 and 1")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for Face GPU training") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for admitted Face GPU training")
    model = build_reference_conditioned_model(default_face_architecture()).to("cuda")
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    return FaceGpuRuntime(
        model=model,
        optimizer=optimizer,
        device="cuda",
        learning_rate=learning_rate,
    )
