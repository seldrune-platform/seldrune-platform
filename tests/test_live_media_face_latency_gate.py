"""Tests for Face interactive latency gating."""
import pytest

from services.live_media.face_latency_gate import FaceLatencyEvidence


def test_latency_rejects_budget_overrun() -> None:
    with pytest.raises(ValueError, match="budget"):
        FaceLatencyEvidence(100.0, 250.0).validate()
