"""Optional PyTorch/CUDA training step for Seldrune Face v0.1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrainingStepResult:
    loss: float
    device: str


def select_training_device(require_cuda: bool = True) -> str:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for Face v0.1 training") from exc
    if torch.cuda.is_available():
        return "cuda"
    if require_cuda:
        raise RuntimeError("CUDA is required for this training run")
    return "cpu"


def train_step(
    model: Any,
    image: Any,
    identity_embedding: Any,
    target: Any,
    optimizer: Any,
    *,
    device: str,
) -> TrainingStepResult:
    """Execute one supervised reconstruction step on an admitted batch."""
    import torch.nn.functional as functional

    model.train()
    image = image.to(device)
    identity_embedding = identity_embedding.to(device)
    target = target.to(device)
    model.to(device)

    optimizer.zero_grad(set_to_none=True)
    prediction = model(image, identity_embedding)
    loss = functional.l1_loss(prediction, target)
    loss.backward()
    optimizer.step()
    return TrainingStepResult(loss=float(loss.detach().cpu().item()), device=device)
