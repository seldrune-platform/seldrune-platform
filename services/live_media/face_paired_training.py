"""Paired source/reference training primitives for Seldrune Face v0.1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PairedTrainingBatch:
    source: Any
    reference: Any
    target: Any

    def validate(self) -> None:
        if self.source is None or self.reference is None or self.target is None:
            raise ValueError("paired training tensors are required")


def paired_train_step(
    model: Any,
    batch: PairedTrainingBatch,
    optimizer: Any,
    *,
    device: str,
) -> float:
    batch.validate()
    try:
        import torch.nn.functional as functional
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for paired Face training") from exc
    model = model.to(device)
    source = batch.source.to(device)
    reference = batch.reference.to(device)
    target = batch.target.to(device)
    optimizer.zero_grad(set_to_none=True)
    output = model(source, reference)
    loss = functional.l1_loss(output, target)
    loss.backward()
    optimizer.step()
    return float(loss.detach().cpu().item())
