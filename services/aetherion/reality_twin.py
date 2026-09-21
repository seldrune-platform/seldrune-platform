"""Bounded counterfactual simulator for Aetherion Reality Compiler research.

The model propagates declared numeric relationships. Its output is simulated
evidence only and cannot establish that a causal relationship exists in nature.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class TwinVariable:
    name: str
    baseline: float
    lower_bound: float
    upper_bound: float

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("variable name is required")
        if self.lower_bound > self.upper_bound:
            raise ValueError(f"invalid bounds for {self.name}")
        if not self.lower_bound <= self.baseline <= self.upper_bound:
            raise ValueError(f"baseline outside bounds for {self.name}")


@dataclass(frozen=True)
class CausalLink:
    source: str
    target: str
    coefficient: float

    def validate(self, names: set[str]) -> None:
        if self.source not in names or self.target not in names:
            raise ValueError("causal link references an unknown variable")
        if self.source == self.target:
            raise ValueError("self-referential causal links are not supported")
        if not -1.0 <= self.coefficient <= 1.0:
            raise ValueError("causal coefficient must be between -1 and 1")


@dataclass(frozen=True)
class Intervention:
    variable: str
    delta: float


@dataclass(frozen=True)
class Guardrail:
    variable: str
    lower_bound: float
    upper_bound: float


@dataclass(frozen=True)
class TwinScenario:
    scenario_id: str
    outcome_variable: str
    steps: int
    interventions: tuple[Intervention, ...]
    guardrails: tuple[Guardrail, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class TwinFrame:
    step: int
    state: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class TwinReceipt:
    scenario_id: str
    outcome_variable: str
    outcome_delta: float
    trajectory: tuple[TwinFrame, ...]
    guardrail_breaches: tuple[str, ...]
    assumptions: tuple[str, ...]
    report_sha256: str
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    causal_model_verified: bool = False
    physical_system_verified: bool = False


def _clamp(value: float, variable: TwinVariable) -> float:
    return min(variable.upper_bound, max(variable.lower_bound, value))


def _validate(
    variables: tuple[TwinVariable, ...],
    links: tuple[CausalLink, ...],
    scenario: TwinScenario,
) -> dict[str, TwinVariable]:
    if not 1 <= len(variables) <= 128:
        raise ValueError("digital twin requires between 1 and 128 variables")
    if len(links) > 1024:
        raise ValueError("digital twin supports at most 1024 causal links")
    if not scenario.scenario_id.strip():
        raise ValueError("scenario_id is required")
    if not 1 <= scenario.steps <= 256:
        raise ValueError("scenario steps must be between 1 and 256")

    by_name = {item.name: item for item in variables}
    if len(by_name) != len(variables):
        raise ValueError("variable names must be unique")
    for variable in variables:
        variable.validate()
    names = set(by_name)
    if scenario.outcome_variable not in names:
        raise ValueError("outcome variable is unknown")
    for link in links:
        link.validate(names)

    intervention_names = tuple(item.variable for item in scenario.interventions)
    if len(set(intervention_names)) != len(intervention_names):
        raise ValueError("interventions must target unique variables")
    if not set(intervention_names).issubset(names):
        raise ValueError("intervention references an unknown variable")
    for guardrail in scenario.guardrails:
        if guardrail.variable not in names:
            raise ValueError("guardrail references an unknown variable")
        if guardrail.lower_bound > guardrail.upper_bound:
            raise ValueError("guardrail lower bound exceeds upper bound")
    return by_name


def _frame(step: int, state: dict[str, float]) -> TwinFrame:
    return TwinFrame(
        step=step,
        state=tuple((name, round(value, 6)) for name, value in sorted(state.items())),
    )


def _digest(
    scenario: TwinScenario,
    trajectory: tuple[TwinFrame, ...],
    breaches: tuple[str, ...],
) -> str:
    payload = {
        "scenario_id": scenario.scenario_id,
        "outcome_variable": scenario.outcome_variable,
        "trajectory": [
            {"step": frame.step, "state": dict(frame.state)} for frame in trajectory
        ],
        "guardrail_breaches": list(breaches),
        "assumptions": list(scenario.assumptions),
        "causal_model_verified": False,
        "physical_system_verified": False,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def simulate_twin(
    variables: tuple[TwinVariable, ...],
    links: tuple[CausalLink, ...],
    scenario: TwinScenario,
) -> TwinReceipt:
    """Propagate one bounded counterfactual scenario deterministically."""
    by_name = _validate(variables, links, scenario)
    baseline = {name: item.baseline for name, item in by_name.items()}
    state = dict(baseline)
    for intervention in scenario.interventions:
        variable = by_name[intervention.variable]
        state[intervention.variable] = _clamp(
            state[intervention.variable] + intervention.delta,
            variable,
        )

    frames = [_frame(0, state)]
    breach_set: set[str] = set()
    for step in range(1, scenario.steps + 1):
        next_state = dict(state)
        for link in links:
            displacement = state[link.source] - baseline[link.source]
            next_state[link.target] += displacement * link.coefficient
        state = {
            name: _clamp(value, by_name[name])
            for name, value in next_state.items()
        }
        for guardrail in scenario.guardrails:
            value = state[guardrail.variable]
            if not guardrail.lower_bound <= value <= guardrail.upper_bound:
                breach_set.add(guardrail.variable)
        frames.append(_frame(step, state))

    trajectory = tuple(frames)
    breaches = tuple(sorted(breach_set))
    final_state = dict(trajectory[-1].state)
    outcome_delta = round(
        final_state[scenario.outcome_variable] - baseline[scenario.outcome_variable],
        6,
    )
    return TwinReceipt(
        scenario_id=scenario.scenario_id,
        outcome_variable=scenario.outcome_variable,
        outcome_delta=outcome_delta,
        trajectory=trajectory,
        guardrail_breaches=breaches,
        assumptions=scenario.assumptions,
        report_sha256=_digest(scenario, trajectory, breaches),
    )
