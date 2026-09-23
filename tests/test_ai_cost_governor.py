from backend.app.core.config import Settings
from backend.app.core.modeling import ModelProvider, ModelRequest, ModelResult
from backend.app.services.ai_cost_governor import (
    estimate_cost_usd,
    external_operation_allowed,
    get_cached_result,
    govern_request,
    projected_cost_exceeds_budget,
    put_cached_result,
    record_spend,
)


def _settings(**overrides):
    values = {
        "ai_cost_governor_enabled": True,
        "ai_default_tier": "economy",
        "ai_economy_model": "gpt-5.6-luna",
        "ai_balanced_model": "gpt-5.6-terra",
        "ai_premium_model": "gpt-5.6-sol",
        "ai_economy_max_output_tokens": 1800,
        "ai_balanced_max_output_tokens": 5000,
        "ai_premium_max_output_tokens": 8000,
        "ai_max_request_cost_usd": 0.25,
        "ai_default_scope_budget_usd": 1.0,
        "ai_cache_ttl_seconds": 900,
    }
    values.update(overrides)
    return Settings(**values)


def test_structured_multimodal_request_routes_to_luna_and_caps_output() -> None:
    settings = _settings()
    request = ModelRequest(
        provider=ModelProvider.OPENAI,
        model="gpt-5.6-sol",
        input_text="Plan this document edit",
        max_output_tokens=6000,
        response_schema={"type": "object"},
    )

    decision = govern_request(settings, request)

    assert decision.tier == "economy"
    assert decision.request.model == "gpt-5.6-luna"
    assert decision.request.max_output_tokens == 1800
    assert decision.routed_from_model == "gpt-5.6-sol"


def test_explicit_balanced_and_premium_tiers_are_available() -> None:
    settings = _settings()
    balanced = govern_request(
        settings,
        ModelRequest(
            provider=ModelProvider.OPENAI,
            model="gpt-5.6-sol",
            input_text="Build an application",
            max_output_tokens=7000,
            metadata={"cost_tier": "balanced"},
        ),
    )
    premium = govern_request(
        settings,
        ModelRequest(
            provider=ModelProvider.OPENAI,
            model="gpt-5.6-luna",
            input_text="Final high-risk architecture review",
            max_output_tokens=12000,
            metadata={"quality_critical": True},
        ),
    )

    assert balanced.request.model == "gpt-5.6-terra"
    assert balanced.request.max_output_tokens == 5000
    assert premium.request.model == "gpt-5.6-sol"
    assert premium.request.max_output_tokens == 8000


def test_current_pricing_makes_luna_far_cheaper_than_sol() -> None:
    luna = estimate_cost_usd(
        "gpt-5.6-luna",
        input_tokens=100_000,
        output_tokens=5_000,
    )
    sol = estimate_cost_usd(
        "gpt-5.6-sol",
        input_tokens=100_000,
        output_tokens=5_000,
    )

    assert luna == 0.026
    assert sol == 0.5
    assert sol / luna > 19


def test_request_budget_blocks_expensive_projected_call_before_generation() -> None:
    settings = _settings(ai_max_request_cost_usd=0.05)
    decision = govern_request(
        settings,
        ModelRequest(
            provider=ModelProvider.OPENAI,
            model="gpt-5.6-sol",
            input_text="expensive",
            max_output_tokens=8000,
            metadata={
                "cost_tier": "premium",
                "max_request_cost_usd": 0.05,
            },
        ),
    )

    blocked, projected, reason = projected_cost_exceeds_budget(
        decision,
        input_tokens=100_000,
    )

    assert blocked is True
    assert projected is not None and projected > 0.05
    assert "per-request budget" in str(reason)


def test_scope_budget_accumulates_real_spend() -> None:
    settings = _settings()
    scope = "test-scope-budget-unique"
    decision = govern_request(
        settings,
        ModelRequest(
            provider=ModelProvider.OPENAI,
            model="gpt-5.6-sol",
            input_text="step",
            max_output_tokens=1000,
            metadata={
                "cost_tier": "economy",
                "cost_scope": scope,
                "scope_budget_usd": 0.01,
            },
        ),
    )
    record_spend(decision, 0.0095)

    blocked, _projected, reason = projected_cost_exceeds_budget(
        decision,
        input_tokens=50_000,
    )

    assert blocked is True
    assert "scope cost" in str(reason)


def test_structured_identical_request_can_be_served_from_zero_cost_cache() -> None:
    settings = _settings()
    request = ModelRequest(
        provider=ModelProvider.OPENAI,
        model="gpt-5.6-luna",
        input_text="same deterministic planner input",
        max_output_tokens=500,
        response_schema={"type": "object"},
    )
    result = ModelResult(
        provider=ModelProvider.OPENAI,
        model="gpt-5.6-luna",
        output_text='{"ok":true}',
        estimated_cost_usd=0.004,
    )

    put_cached_result(settings, request, result)
    cached = get_cached_result(settings, request)

    assert cached is not None
    assert cached.output_text == result.output_text
    assert cached.cache_hit is True
    assert cached.estimated_cost_usd == 0.0


def test_future_media_operation_can_be_rejected_by_budget_before_call() -> None:
    settings = _settings()

    allowed, reason = external_operation_allowed(
        settings,
        estimated_cost_usd=2.50,
        budget_usd=0.50,
    )

    assert allowed is False
    assert "exceeds" in str(reason)
