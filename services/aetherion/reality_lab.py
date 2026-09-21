"""Falsifiable experiment and calibration gate for Reality Compiler research.

Measurements can make a model eligible for independent review. Software alone
never promotes a causal model or physical system to verified status.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum

from .qgpu_model import EvidenceLevel


class CalibrationDecision(StrEnum):
    INSUFFICIENT_DATA = "insufficient-data"
    REJECTED = "rejected"
    ELIGIBLE_FOR_REVIEW = "eligible-for-independent-review"


@dataclass(frozen=True)
class ExperimentProtocol:
    protocol_id: str
    source_variable: str
    target_variable: str
    input_unit: str
    output_unit: str
    minimum_observations: int
    minimum_r_squared: float
    slope_lower_bound: float
    slope_upper_bound: float
    safety_notes: tuple[str, ...]

    def validate(self) -> None:
        required = (
            self.protocol_id,
            self.source_variable,
            self.target_variable,
            self.input_unit,
            self.output_unit,
        )
        if any(not item.strip() for item in required):
            raise ValueError("protocol identity, variables, and units are required")
        if not 3 <= self.minimum_observations <= 10_000:
            raise ValueError("minimum observations must be between 3 and 10000")
        if not 0.0 <= self.minimum_r_squared <= 1.0:
            raise ValueError("minimum_r_squared must be normalized")
        if self.slope_lower_bound > self.slope_upper_bound:
            raise ValueError("slope lower bound exceeds upper bound")
        if not self.safety_notes:
            raise ValueError("at least one safety note is required")


@dataclass(frozen=True)
class Measurement:
    measurement_id: str
    input_value: float
    output_value: float
    evidence_sha256: str

    def validate(self) -> None:
        if not self.measurement_id.strip():
            raise ValueError("measurement_id is required")
        if not math.isfinite(self.input_value) or not math.isfinite(self.output_value):
            raise ValueError("measurement values must be finite")
        if len(self.evidence_sha256) != 64:
            raise ValueError("evidence_sha256 must contain 64 hexadecimal characters")
        try:
            int(self.evidence_sha256, 16)
        except ValueError as exc:
            raise ValueError(
                "evidence_sha256 must contain 64 hexadecimal characters"
            ) from exc


@dataclass(frozen=True)
class CalibrationReceipt:
    protocol_id: str
    decision: CalibrationDecision
    observation_count: int
    slope: float | None
    intercept: float | None
    r_squared: float | None
    slope_within_bounds: bool
    evidence_artifacts: tuple[str, ...]
    report_sha256: str
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    independently_replicated: bool = False
    causal_model_verified: bool = False
    physical_system_verified: bool = False


def _linear_fit(
    measurements: tuple[Measurement, ...],
) -> tuple[float | None, float | None, float | None]:
    if len(measurements) < 2:
        return None, None, None
    mean_x = sum(item.input_value for item in measurements) / len(measurements)
    mean_y = sum(item.output_value for item in measurements) / len(measurements)
    variance_x = sum((item.input_value - mean_x) ** 2 for item in measurements)
    if variance_x == 0:
        return None, None, None

    covariance = sum(
        (item.input_value - mean_x) * (item.output_value - mean_y)
        for item in measurements
    )
    slope = covariance / variance_x
    intercept = mean_y - slope * mean_x
    residual_sum = sum(
        (item.output_value - (slope * item.input_value + intercept)) ** 2
        for item in measurements
    )
    total_sum = sum((item.output_value - mean_y) ** 2 for item in measurements)
    r_squared = 1.0 if total_sum == 0 and residual_sum == 0 else 0.0
    if total_sum > 0:
        r_squared = max(0.0, min(1.0, 1.0 - residual_sum / total_sum))
    return round(slope, 8), round(intercept, 8), round(r_squared, 8)


def _digest(
    protocol: ExperimentProtocol,
    measurements: tuple[Measurement, ...],
    decision: CalibrationDecision,
    slope: float | None,
    intercept: float | None,
    r_squared: float | None,
) -> str:
    payload = {
        "protocol": {
            "id": protocol.protocol_id,
            "source": protocol.source_variable,
            "target": protocol.target_variable,
            "input_unit": protocol.input_unit,
            "output_unit": protocol.output_unit,
            "minimum_observations": protocol.minimum_observations,
            "minimum_r_squared": protocol.minimum_r_squared,
            "slope_bounds": [
                protocol.slope_lower_bound,
                protocol.slope_upper_bound,
            ],
            "safety_notes": list(protocol.safety_notes),
        },
        "measurements": [
            {
                "id": item.measurement_id,
                "input": item.input_value,
                "output": item.output_value,
                "evidence_sha256": item.evidence_sha256,
            }
            for item in measurements
        ],
        "decision": decision.value,
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "independently_replicated": False,
        "causal_model_verified": False,
        "physical_system_verified": False,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def calibrate_experiment(
    protocol: ExperimentProtocol,
    measurements: tuple[Measurement, ...],
) -> CalibrationReceipt:
    """Evaluate linked observations without asserting physical verification."""
    protocol.validate()
    if len(measurements) > 10_000:
        raise ValueError("at most 10000 measurements are supported")
    ids = tuple(item.measurement_id for item in measurements)
    if len(set(ids)) != len(ids):
        raise ValueError("measurement ids must be unique")
    for measurement in measurements:
        measurement.validate()

    slope, intercept, r_squared = _linear_fit(measurements)
    within_bounds = (
        slope is not None
        and protocol.slope_lower_bound <= slope <= protocol.slope_upper_bound
    )
    if len(measurements) < protocol.minimum_observations:
        decision = CalibrationDecision.INSUFFICIENT_DATA
    elif (
        r_squared is not None
        and r_squared >= protocol.minimum_r_squared
        and within_bounds
    ):
        decision = CalibrationDecision.ELIGIBLE_FOR_REVIEW
    else:
        decision = CalibrationDecision.REJECTED

    digest = _digest(
        protocol,
        measurements,
        decision,
        slope,
        intercept,
        r_squared,
    )
    return CalibrationReceipt(
        protocol_id=protocol.protocol_id,
        decision=decision,
        observation_count=len(measurements),
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        slope_within_bounds=within_bounds,
        evidence_artifacts=tuple(item.evidence_sha256 for item in measurements),
        report_sha256=digest,
    )
