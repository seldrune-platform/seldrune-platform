"""Deterministic Face v0.1 execution plan."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FaceRunPlan:
    stages: tuple[str,...]=(
        "dataset-audit","preprocess","cuda-train","checkpoint-verify",
        "onnx-export","onnx-verify","liveshift-load","first-frame",
    )
    def validate(self) -> None:
        if len(set(self.stages)) != len(self.stages):
            raise ValueError("run stages must be unique")
