import pytest

from services.supreme.verifiers import (
    CheckState,
    all_checks_pass,
    threshold_check,
)


def test_quality_threshold_passes():
    check = threshold_check("accuracy", 0.91, 0.85, "artifact://accuracy.json")
    assert check.state is CheckState.PASS


def test_latency_uses_lower_is_better():
    check = threshold_check(
        "latency-ms",
        145.0,
        200.0,
        "artifact://latency.json",
        lower_is_better=True,
    )
    assert check.state is CheckState.PASS


def test_failed_check_blocks_mesh():
    checks = (
        threshold_check("quality", 0.9, 0.8, "artifact://quality"),
        threshold_check("success", 0.6, 0.8, "artifact://success"),
    )
    assert not all_checks_pass(checks)


def test_verifier_requires_real_evidence_reference():
    with pytest.raises(ValueError, match="evidence"):
        threshold_check("accuracy", 0.9, 0.8, "")
