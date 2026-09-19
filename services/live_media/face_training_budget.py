"""Hard GPU-dollar budget guard for Face training."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FaceGpuBudget:
    usd_limit: float
    hourly_usd: float
    reserve_fraction: float=0.15
    def validate(self) -> None:
        if self.usd_limit <= 0 or self.hourly_usd <= 0 or not 0 <= self.reserve_fraction < 1:
            raise ValueError("invalid GPU budget")
    @property
    def max_gpu_hours(self) -> float:
        self.validate()
        return self.usd_limit*(1-self.reserve_fraction)/self.hourly_usd
