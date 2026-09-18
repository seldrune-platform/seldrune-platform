"""Conservative capacity tiers for the preferred Seldrune accelerator."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MediaCapacity:
    warm_model_budget_gb: int
    session_budget_gb: int
    reserve_gb: int

    def max_sessions(self, total_vram_gb: int) -> int:
        usable = total_vram_gb - self.warm_model_budget_gb - self.reserve_gb
        if usable <= 0 or self.session_budget_gb <= 0:
            return 0
        return usable // self.session_budget_gb


DEFAULT_RTX_PRO_6000_CAPACITY = MediaCapacity(
    warm_model_budget_gb=32,
    session_budget_gb=8,
    reserve_gb=16,
)
