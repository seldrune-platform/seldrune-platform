from __future__ import annotations

import pytest

from backend.app.core.modeling import (
    ModelGatewayError,
    ModelProvider,
    ModelRoutePerformanceEvidence,
)
from backend.app.services.cost_aware_model_router import (
    CostAwareModelCandidate,
    select_cost_aware_model_route,
)


def _evidence(
    provider: ModelProvider,
    model: str,
    outcomes: tuple[bool, ...],
    *,
    prefix: str,
):
    return tuple(
        ModelRoutePerformanceEvidence(
            provider=provider,
            model=model,
            succeeded=outcome,
            age_seconds=index * 600,
            evidence_key=f"{prefix}:{index}",
            evidence_refs=(f"receipt:{prefix}:{index}",),
            verified=True,
        )
        for index, outcome in enumerate(outcomes)
    )


def test_cost_aware_router_chooses_cheapest_route_above_quality_floor() -> None:
    evidence = (
        *_evidence(
            ModelProvider.OPENAI,
            "gpt-5.6-luna",
            (True, False, False, True),
            prefix="luna",
        ),
        *_evidence(
            ModelProvider.OPENAI,
            "gpt-5.6-terra",
            (True, True, True, True),
            prefix="terra",
        ),
        *_evidence(
            ModelProvider.OPENAI,
            "gpt-5.6-sol",
            (True, True, True, True),
            prefix="sol",
        ),
    )

    decision = select_cost_aware_model_route(
        candidates=(
            CostAwareModelCandidate(
                provider=ModelProvider.OPENAI,
                model="gpt-5.6-luna",
                verification_reserve_usd=0.005,
            ),
            CostAwareModelCandidate(
                provider=ModelProvider.OPENAI,
                model="gpt-5.6-terra",
                verification_reserve_usd=0.005,
            ),
            CostAwareModelCandidate(
                provider=ModelProvider.OPENAI,
                model="gpt-5.6-sol",
                verification_reserve_usd=0.005,
            ),
        ),
        performance_evidence=evidence,
        required_capabilities=("text", "reasoning"),
        projected_input_tokens=10_000,
        projected_output_tokens=2_000,
        max_total_cost_usd=0.10,
        minimum_trust=0.80,
        max_projected_risk=0.20,
    )

    assert decision.model == "gpt-5.6-terra"
    assert decision.trust_score == 1.0
    assert decision.projected_total_cost_usd < 0.10
    assert decision.evidence_refs


def test_total_cost_includes_independent_verification_reserve() -> None:
    evidence = (
        *_evidence(
            ModelProvider.OPENAI_COMPATIBLE,
            "local-a",
            (True, True, True),
            prefix="a",
        ),
        *_evidence(
            ModelProvider.OPENAI_COMPATIBLE,
            "local-b",
            (True, True, True),
            prefix="b",
        ),
    )
    decision = select_cost_aware_model_route(
        candidates=(
            CostAwareModelCandidate(
                provider=ModelProvider.OPENAI_COMPATIBLE,
                model="local-a",
                generation_cost_override_usd=0.005,
                verification_reserve_usd=0.04,
            ),
            CostAwareModelCandidate(
                provider=ModelProvider.OPENAI_COMPATIBLE,
                model="local-b",
                generation_cost_override_usd=0.02,
                verification_reserve_usd=0.005,
            ),
        ),
        performance_evidence=evidence,
        required_capabilities=("text",),
        projected_input_tokens=2_000,
        projected_output_tokens=500,
        max_total_cost_usd=0.05,
    )

    assert decision.model == "local-b"
    assert decision.generation_cost_usd == 0.02
    assert decision.verification_reserve_usd == 0.005
    assert decision.projected_total_cost_usd == 0.025


def test_unverified_or_low_trust_routes_fail_closed() -> None:
    with pytest.raises(ModelGatewayError, match="No verified model route"):
        select_cost_aware_model_route(
            candidates=(
                CostAwareModelCandidate(
                    provider=ModelProvider.OPENAI,
                    model="gpt-5.6-luna",
                ),
            ),
            performance_evidence=(),
            required_capabilities=("text",),
            projected_input_tokens=1000,
            projected_output_tokens=200,
            max_total_cost_usd=0.10,
        )

    evidence = _evidence(
        ModelProvider.OPENAI,
        "gpt-5.6-luna",
        (False, False, True),
        prefix="weak",
    )
    with pytest.raises(ModelGatewayError, match="No verified model route"):
        select_cost_aware_model_route(
            candidates=(
                CostAwareModelCandidate(
                    provider=ModelProvider.OPENAI,
                    model="gpt-5.6-luna",
                ),
            ),
            performance_evidence=evidence,
            required_capabilities=("text",),
            projected_input_tokens=1000,
            projected_output_tokens=200,
            max_total_cost_usd=0.10,
            minimum_trust=0.80,
        )


def test_unknown_price_requires_explicit_cost_override() -> None:
    evidence = _evidence(
        ModelProvider.OPENAI_COMPATIBLE,
        "local-cheap",
        (True, True, True),
        prefix="local",
    )

    with pytest.raises(ModelGatewayError, match="No verified model route"):
        select_cost_aware_model_route(
            candidates=(
                CostAwareModelCandidate(
                    provider=ModelProvider.OPENAI_COMPATIBLE,
                    model="local-cheap",
                ),
            ),
            performance_evidence=evidence,
            required_capabilities=("text",),
            projected_input_tokens=1000,
            projected_output_tokens=200,
            max_total_cost_usd=0.10,
        )
