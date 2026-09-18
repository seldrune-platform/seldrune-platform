from dataclasses import dataclass


@dataclass(frozen=True)
class LatencyBudget:
    capture_ms: int = 15
    uplink_ms: int = 35
    inference_ms: int = 45
    encode_ms: int = 15
    downlink_ms: int = 35

    @property
    def total_ms(self) -> int:
        return (
            self.capture_ms
            + self.uplink_ms
            + self.inference_ms
            + self.encode_ms
            + self.downlink_ms
        )

    @property
    def interactive(self) -> bool:
        return self.total_ms <= 200
