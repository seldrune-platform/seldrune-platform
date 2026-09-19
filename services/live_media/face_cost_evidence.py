"""GPU cost evidence for Face training."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FaceCostEvidence:
    gpu_hourly_usd: float
    training_hours: float

    @property
    def training_cost_usd(self) -> float:
        return self.gpu_hourly_usd * self.training_hours

    def validate(self) -> None:
        if self.gpu_hourly_usd <= 0 or self.training_hours <= 0:
            raise ValueError("GPU cost evidence must use positive measured values")
