"""Explicit client-side receipt telemetry for production Face sessions."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol


@dataclass(frozen=True)
class ClientVideoReceipt:
    """One video frame receipt measured at the receiving client."""

    latency_ms: float

    def validate(self) -> None:
        if not math.isfinite(self.latency_ms) or self.latency_ms <= 0:
            raise ValueError("client video receipt latency must be positive")


class ClientReceiptObserver(Protocol):
    """Sink for measurements that originate at the receiving client only."""

    def record_client_received_frame(self, latency_ms: float) -> None: ...


def record_client_video_receipt(
    observer: ClientReceiptObserver,
    receipt: ClientVideoReceipt,
) -> None:
    """Forward validated client telemetry without deriving it from server timing."""
    receipt.validate()
    observer.record_client_received_frame(receipt.latency_ms)
