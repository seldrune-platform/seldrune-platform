import pytest

from backend.app.api.routes.aetherion import reality_twin_demo
from services.aetherion.qgpu_model import EvidenceLevel
from services.aetherion.reality_twin import (
    CausalLink,
    Guardrail,
    Intervention,
    TwinScenario,
    TwinVariable,
    simulate_twin,
)


def _variables() -> tuple[TwinVariable, ...]:
    return (
        TwinVariable("input", 10.0, 0.0, 30.0),
        TwinVariable("output", 2.0, 0.0, 20.0),
        TwinVariable("risk", 0.1, 0.0, 1.0),
    )


def test_twin_runs_deterministic_counterfactual_without_physical_claims():
    scenario = TwinScenario(
        scenario_id="bounded-test",
        outcome_variable="output",
        steps=2,
        interventions=(Intervention("input", 5.0),),
        guardrails=(Guardrail("risk", 0.0, 0.5),),
        assumptions=("linear response inside the declared operating range",),
    )
    links = (
        CausalLink("input", "output", 0.2),
        CausalLink("input", "risk", 0.01),
    )

    first = simulate_twin(_variables(), links, scenario)
    second = simulate_twin(_variables(), links, scenario)

    assert first.outcome_delta == 2.0
    assert first.report_sha256 == second.report_sha256
    assert first.evidence is EvidenceLevel.EXPERIMENTAL
    assert not first.causal_model_verified
    assert not first.physical_system_verified
    assert not first.guardrail_breaches


def test_twin_reports_guardrail_breach():
    scenario = TwinScenario(
        scenario_id="risk-test",
        outcome_variable="output",
        steps=2,
        interventions=(Intervention("input", 20.0),),
        guardrails=(Guardrail("risk", 0.0, 0.2),),
    )
    receipt = simulate_twin(
        _variables(),
        (CausalLink("input", "risk", 0.02),),
        scenario,
    )

    assert receipt.guardrail_breaches == ("risk",)


def test_twin_rejects_unknown_variables_and_unbounded_steps():
    invalid_link = CausalLink("missing", "output", 0.2)
    scenario = TwinScenario("invalid", "output", 1, ())

    with pytest.raises(ValueError, match="unknown variable"):
        simulate_twin(_variables(), (invalid_link,), scenario)

    too_long = TwinScenario("too-long", "output", 257, ())
    with pytest.raises(ValueError, match="between 1 and 256"):
        simulate_twin(_variables(), (), too_long)


def test_twin_demo_endpoint_preserves_truth_boundary():
    payload = reality_twin_demo()

    assert payload["status"] == "experimental"
    assert payload["trajectory"]
    assert not payload["causal_model_verified"]
    assert not payload["physical_system_verified"]
