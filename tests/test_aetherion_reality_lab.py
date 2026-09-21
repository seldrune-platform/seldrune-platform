import pytest

from backend.app.api.routes.aetherion import reality_lab_demo
from services.aetherion.qgpu_model import EvidenceLevel
from services.aetherion.reality_lab import (
    CalibrationDecision,
    ExperimentProtocol,
    Measurement,
    calibrate_experiment,
)


def _protocol() -> ExperimentProtocol:
    return ExperimentProtocol(
        protocol_id="thermal-response-v1",
        source_variable="temperature_delta",
        target_variable="efficiency_delta",
        input_unit="kelvin",
        output_unit="ratio",
        minimum_observations=4,
        minimum_r_squared=0.95,
        slope_lower_bound=1.8,
        slope_upper_bound=2.2,
        safety_notes=("Stop the experiment if the declared thermal limit is reached.",),
    )


def _measurement(index: int, output: float) -> Measurement:
    return Measurement(
        measurement_id=f"run-{index}",
        input_value=float(index),
        output_value=output,
        evidence_sha256=f"{index:064x}",
    )


def test_calibration_can_be_eligible_without_becoming_verified():
    measurements = tuple(
        _measurement(index, 2.0 * index + 1.0)
        for index in range(1, 5)
    )
    receipt = calibrate_experiment(_protocol(), measurements)

    assert receipt.decision is CalibrationDecision.ELIGIBLE_FOR_REVIEW
    assert receipt.slope == 2.0
    assert receipt.r_squared == 1.0
    assert receipt.evidence is EvidenceLevel.EXPERIMENTAL
    assert not receipt.independently_replicated
    assert not receipt.causal_model_verified
    assert not receipt.physical_system_verified
    assert len(receipt.report_sha256) == 64


def test_calibration_reports_insufficient_observations():
    receipt = calibrate_experiment(
        _protocol(),
        (_measurement(1, 3.0), _measurement(2, 5.0)),
    )

    assert receipt.decision is CalibrationDecision.INSUFFICIENT_DATA
    assert receipt.observation_count == 2


def test_calibration_rejects_slope_outside_protocol():
    measurements = tuple(
        _measurement(index, 4.0 * index)
        for index in range(1, 5)
    )
    receipt = calibrate_experiment(_protocol(), measurements)

    assert receipt.decision is CalibrationDecision.REJECTED
    assert not receipt.slope_within_bounds


def test_measurement_requires_content_addressed_evidence():
    invalid = Measurement("run", 1.0, 2.0, "not-a-sha")

    with pytest.raises(ValueError, match="64 hexadecimal"):
        calibrate_experiment(_protocol(), (invalid,))


def test_reality_lab_demo_endpoint_requires_independent_review():
    payload = reality_lab_demo()

    assert payload["decision"] == "eligible-for-independent-review"
    assert payload["r_squared"] == 1.0
    assert not payload["independently_replicated"]
    assert not payload["causal_model_verified"]
    assert not payload["physical_system_verified"]
