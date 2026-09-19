"""Basic numerical quality gate for trained Face outputs."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class FaceQualityEvidence:
    loss: float
    def validate(self) -> None:
        if not math.isfinite(self.loss) or self.loss < 0:
            raise ValueError("training loss must be finite and non-negative")
