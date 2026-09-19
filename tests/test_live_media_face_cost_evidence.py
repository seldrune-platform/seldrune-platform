"""Tests for Face GPU cost evidence."""
from services.live_media.face_cost_evidence import FaceCostEvidence


def test_training_cost_is_measured_from_hours() -> None:
    evidence = FaceCostEvidence(2.10, 2.0)
    evidence.validate()
    assert evidence.training_cost_usd == 4.20
