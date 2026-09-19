"""Small benchmark summary for Face v0.1 runtime evidence."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FaceBenchmark:
    samples: int
    average_ms: float
    p95_ms: float

    @property
    def estimated_fps(self) -> float:
        return 1000.0 / self.average_ms if self.average_ms > 0 else 0.0

    def validate(self) -> None:
        if self.samples < 1 or self.average_ms <= 0 or self.p95_ms <= 0:
            raise ValueError("benchmark requires measured positive samples and latency")
        if self.p95_ms < self.average_ms:
            raise ValueError("p95 latency cannot be below average latency")
