"""State-space reduction model for the integrated QGPU engine."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class StateSpaceReceipt:
    candidate_states: int
    reusable_states: int
    sparse_states: int
    surviving_states: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_superposition_verified: bool = False


def reduce_state_space(candidate_states: int, reusable: int, sparse: int) -> StateSpaceReceipt:
    if min(candidate_states, reusable, sparse) < 0:
        raise ValueError("state counts must be non-negative")
    eliminated = min(candidate_states, reusable + sparse)
    return StateSpaceReceipt(
        candidate_states,
        reusable,
        sparse,
        candidate_states - eliminated,
    )
