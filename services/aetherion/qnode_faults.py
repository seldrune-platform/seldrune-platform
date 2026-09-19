"""Fault isolation for concurrent Aetherion research nodes."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class FaultReceipt:
    succeeded: tuple[str, ...]
    failed: tuple[str, ...]
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


def classify(results: dict[str, BaseException | int]) -> FaultReceipt:
    failed = tuple(
        sorted(
            name
            for name, value in results.items()
            if isinstance(value, BaseException)
        )
    )
    succeeded = tuple(
        sorted(
            name
            for name, value in results.items()
            if not isinstance(value, BaseException)
        )
    )
    return FaultReceipt(succeeded, failed)
