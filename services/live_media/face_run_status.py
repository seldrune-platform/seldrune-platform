"""Truthful Face v0.1 milestone state."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FaceRunStatus:
    gpu_training_completed: bool=False
    checkpoint_verified: bool=False
    onnx_exported: bool=False
    liveshift_loaded: bool=False
    first_frame_transformed: bool=False

    @property
    def first_real_output_ready(self) -> bool:
        return all((self.gpu_training_completed,self.checkpoint_verified,self.onnx_exported,self.liveshift_loaded,self.first_frame_transformed))
