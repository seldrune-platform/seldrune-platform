"""Interactive latency gate for LiveShift Face."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FaceLatencyEvidence:
    average_ms: float
    p95_ms: float
    budget_ms: float = 200.0

    def validate(self) -> None:
        if self.average_ms <= 0 or self.p95_ms <= 0:
            raise ValueError("latency measurements must be positive")
        if self.p95_ms < self.average_ms:
            raise ValueError("p95 latency cannot be below average")
        if self.p95_ms > self.budget_ms:
            raise ValueError("LiveShift latency budget exceeded")
