"""Paired source/reference training primitives for Seldrune Face v0.1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .face_torch_training import TrainingStepResult


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
    precision: str = "bf16",
) -> TrainingStepResult:
    """Train the reference-conditioned model on one source/reference/target batch."""
    batch.validate()
    try:
        import torch
        import torch.nn.functional as functional
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for paired Face training") from exc
    if precision not in {"fp32", "fp16", "bf16"}:
        raise ValueError("unsupported training precision")

    model = model.to(device)
    model.train()
    source = batch.source.to(device)
    reference = batch.reference.to(device)
    target = batch.target.to(device)
    optimizer.zero_grad(set_to_none=True)

    use_amp = device == "cuda" and precision in {"fp16", "bf16"}
    amp_dtype = torch.bfloat16 if precision == "bf16" else torch.float16
    with torch.autocast(device_type="cuda", dtype=amp_dtype, enabled=use_amp):
        output = model(source, reference)
        reconstruction = functional.l1_loss(output, target)
    reconstruction.backward()
    optimizer.step()
    return TrainingStepResult(
        loss=float(reconstruction.detach().float().cpu().item()),
        device=device,
    )
