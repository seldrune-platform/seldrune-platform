"""Tests for Face runtime benchmark evidence."""
from services.live_media.face_benchmark import FaceBenchmark


def test_benchmark_estimates_fps() -> None:
    result = FaceBenchmark(samples=100, average_ms=20.0, p95_ms=30.0)
    result.validate()
    assert result.estimated_fps == 50.0
