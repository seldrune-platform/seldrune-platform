"""In-memory evidence history for experimental Aetherion runs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvidenceHistory:
    limit: int = 50
    _items: list[dict[str, object]] = field(default_factory=list)

    def append(self, snapshot: dict[str, object]) -> None:
        self._items.append(dict(snapshot))
        if len(self._items) > self.limit:
            del self._items[: len(self._items) - self.limit]

    def latest(self) -> dict[str, object] | None:
        return dict(self._items[-1]) if self._items else None

    def items(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(item) for item in self._items)
