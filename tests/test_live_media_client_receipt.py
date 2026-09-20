"""Tests for explicit client-side production receipt telemetry."""

import pytest

from services.live_media.client_receipt import (
    ClientVideoReceipt,
    record_client_video_receipt,
)


class _Observer:
    def __init__(self) -> None:
        self.latencies: list[float] = []

    def record_client_received_frame(self, latency_ms: float) -> None:
        self.latencies.append(latency_ms)


def test_valid_client_receipt_is_forwarded() -> None:
    observer = _Observer()

    record_client_video_receipt(observer, ClientVideoReceipt(latency_ms=42.5))

    assert observer.latencies == [42.5]


@pytest.mark.parametrize("latency_ms", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_client_receipt_is_rejected(latency_ms: float) -> None:
    observer = _Observer()

    with pytest.raises(ValueError, match="latency must be positive"):
        record_client_video_receipt(observer, ClientVideoReceipt(latency_ms=latency_ms))

    assert observer.latencies == []
