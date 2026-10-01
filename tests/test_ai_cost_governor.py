import pytest

from backend.app.core.config import Settings
from backend.app.core.modeling import ModelProvider, ModelRequest
from backend.app.services.ai_cost_governor import (
    apply_budget_pressure,
    choose_cost_route,
    estimate_model_cost,
)
from backend.app.services.model_gateway import (
    ModelGateway,
    ModelGatewayError,
    _is_prompt_cache_error,
    normalize_prompt_cache_key,
)


def _settings(**overrides) -> Settings:
    return Settings(
        model_provider="openai",
        model_default="gpt-5.6-sol",
        model_economy="gpt-5.6-luna",
        model_balanced="gpt-5.6-terra",
        model_premium="gpt-5.6-sol",
        **overrides,
    )


def test_economy_router_uses_luna_for_simple_and_planning_work() -> None:
    settings = _settings()

    chat = choose_cost_route(
        settings,
        purpose="chat",
        text="Summarize this short note.",
    )
    planner = choose_cost_route(
        settings,
        purpose="planner",
        text="Create a three step plan.",
    )

    assert chat.model == "gpt-5.6-luna"
    assert chat.tier == "economy"
    assert planner.model == "gpt-5.6-luna"
    assert planner.request_budget_usd <= 0.015


def test_router_escalates_complex_work_without_defaulting_everything_to_sol() -> None:
    settings = _settings()

    medium = choose_cost_route(
        settings,
        purpose="chat",
        text=(
            "Debug this production database migration and refactor the integration "
            "architecture."
        ),
        has_files=True,
    )
    hard = choose_cost_route(
        settings,
        purpose="chat",
        text=(
            "Perform root cause analysis for a critical production security incident "
            "in a distributed system architecture."
        ),
        has_files=True,
    )

    assert medium.model == "gpt-5.6-luna"
    assert medium.tier == "economy"
    assert hard.model == "gpt-5.6-terra"
    assert hard.tier == "balanced"

    critical = choose_cost_route(
        settings,
        purpose="agent",
        text=(
            "Perform root cause analysis for a critical production security incident "
            "in a distributed system architecture."
        ),
        has_files=True,
        capabilities=["security"],
    )
    assert critical.model == "gpt-5.6-sol"
    assert critical.tier == "premium"


def test_pdf_retries_use_luna_then_terra_and_never_need_sol_by_default() -> None:
    settings = _settings()

    first = choose_cost_route(
        settings,
        purpose="pdf",
        text="Change three salary values.",
        attempt=0,
        has_files=True,
    )
    second = choose_cost_route(
        settings,
        purpose="pdf",
        text="Change three salary values.",
        attempt=1,
        has_images=True,
    )
    last = choose_cost_route(
        settings,
        purpose="pdf",
        text="Change three salary values.",
        attempt=2,
        has_images=True,
    )

    assert first.model == "gpt-5.6-luna"
    assert second.model == "gpt-5.6-luna"
    assert last.model == "gpt-5.6-terra"
    assert first.max_output_tokens == 2200
    assert second.max_output_tokens == 1400


def test_known_model_cost_estimate_accounts_for_cache_discount() -> None:
    uncached = estimate_model_cost(
        "gpt-5.6-luna",
        input_tokens=100_000,
        output_tokens=10_000,
    )
    cached = estimate_model_cost(
        "gpt-5.6-luna",
        input_tokens=100_000,
        output_tokens=10_000,
        cached_input_tokens=90_000,
    )

    assert uncached == pytest.approx(0.032, abs=0.000001)
    assert cached == pytest.approx(0.0158, abs=0.000001)
    assert cached < uncached


def test_astra_cost_estimate_uses_official_standard_rates() -> None:
    uncached = estimate_model_cost(
        "gpt-6-astra",
        input_tokens=100_000,
        output_tokens=10_000,
    )
    cached = estimate_model_cost(
        "gpt-6-astra",
        input_tokens=100_000,
        output_tokens=10_000,
        cached_input_tokens=90_000,
    )

    assert uncached == pytest.approx(1.5, abs=0.000001)
    assert cached == pytest.approx(0.69, abs=0.000001)
    assert cached < uncached


def test_gateway_budget_guard_blocks_expensive_request_before_generation() -> None:
    settings = _settings()
    gateway = ModelGateway(settings)
    request = ModelRequest(
        provider=ModelProvider.OPENAI,
        model="gpt-5.6-sol",
        input_text="expensive",
        max_output_tokens=10_000,
        max_estimated_cost_usd=0.05,
    )

    with pytest.raises(ModelGatewayError, match="cost governor blocked"):
        gateway._guard_request_cost(request, input_tokens=100_000)


def test_governor_can_be_disabled_for_explicit_legacy_behavior() -> None:
    settings = _settings(ai_cost_governor_enabled=False)

    route = choose_cost_route(
        settings,
        purpose="chat",
        text="hello",
    )

    assert route.model == "gpt-5.6-sol"
    assert route.tier == "configured"
    assert route.pdf_detail == "auto"


def test_budget_pressure_forces_conservation_to_luna() -> None:
    settings = _settings(
        ai_spend_warning_ratio=0.70,
        ai_conservation_ratio=0.80,
    )
    premium = choose_cost_route(
        settings,
        purpose="agent",
        text=(
            "Perform root cause analysis for a critical production security incident "
            "in a distributed system architecture."
        ),
        has_files=True,
        capabilities=["security"],
    )

    route = apply_budget_pressure(
        settings,
        premium,
        monthly_utilization=0.85,
    )

    assert route.model == "gpt-5.6-luna"
    assert route.tier == "conservation"
    assert route.request_budget_usd <= 0.02
    assert route.max_output_tokens <= 600


def test_prompt_cache_key_keeps_short_key_unchanged() -> None:
    key = "seldrune:org:gpt"

    assert normalize_prompt_cache_key(key) == key


def test_prompt_cache_key_hashes_long_pdf_filename_to_openai_limit() -> None:
    key = (
        "seldrune:12345678-1234-1234-1234-123456789012:pdf:"
        "an-extremely-long-offer-letter-and-annexure-final-version-2026.pdf"
    )

    normalized = normalize_prompt_cache_key(key)

    assert len(normalized) <= 64
    assert normalized != key
    assert normalized == normalize_prompt_cache_key(key)
    assert normalized.startswith("seldrune:")


def test_prompt_cache_error_detection_is_specific() -> None:
    assert _is_prompt_cache_error(
        ValueError("Invalid 'prompt_cache_key': string too long")
    )
    assert _is_prompt_cache_error(
        ValueError("prompt_cache_options is unsupported")
    )
    assert not _is_prompt_cache_error(ValueError("rate limit exceeded"))
