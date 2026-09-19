"""Bounded content-addressed Q-Memory research cache."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class QMemoryV2Receipt:
    hits: int
    misses: int
    evictions: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


class QMemoryV2:
    def __init__(self, capacity: int = 128):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._states: OrderedDict[str, bytes] = OrderedDict()
        self.hits = self.misses = self.evictions = 0

    def get(self, key: str) -> bytes | None:
        value = self._states.get(key)
        if value is None:
            self.misses += 1
            return None
        self.hits += 1
        self._states.move_to_end(key)
        return value

    def put(self, key: str, value: bytes) -> None:
        if key in self._states:
            self._states.move_to_end(key)
        self._states[key] = value
        if len(self._states) > self.capacity:
            self._states.popitem(last=False)
            self.evictions += 1

    def receipt(self) -> QMemoryV2Receipt:
        return QMemoryV2Receipt(self.hits, self.misses, self.evictions)
