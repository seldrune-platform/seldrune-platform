from dataclasses import dataclass


@dataclass(frozen=True)
class ReconnectPolicy:
    max_attempts: int = 5
    base_delay_ms: int = 250
    max_delay_ms: int = 4000

    def delay_ms(self, attempt: int) -> int:
        if attempt < 0:
            raise ValueError("attempt must be non-negative")
        delay = self.base_delay_ms * (2**attempt)
        return min(delay, self.max_delay_ms)
