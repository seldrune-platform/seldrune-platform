"""State-budget admission model for Aetherion QGPU research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class StateBudgetReceipt:
    requested_states: int
    admitted_states: int
    deferred_states: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def apply_state_budget(requested_states: int, budget: int) -> StateBudgetReceipt:
    if requested_states < 0 or budget < 0:
        raise ValueError("state counts must be non-negative")
    admitted = min(requested_states, budget)
    return StateBudgetReceipt(requested_states, admitted, requested_states - admitted)
