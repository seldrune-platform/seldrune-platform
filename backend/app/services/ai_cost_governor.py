from collections.abc import Iterable
from dataclasses import dataclass

from backend.app.core.config import Settings


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    cached_input_per_million: float
    cache_write_per_million: float
    output_per_million: float


# Current OpenAI standard short-context rates. These are used only for
# Seldrune's local safety estimates; provider billing remains authoritative.
MODEL_PRICES: dict[str, ModelPrice] = {
    "gpt-5.6-luna": ModelPrice(0.20, 0.02, 0.25, 1.20),
    "gpt-5.6-terra": ModelPrice(2.00, 0.20, 2.50, 12.00),
    "gpt-5.6-sol": ModelPrice(4.00, 0.40, 5.00, 20.00),
    "gpt-5.6": ModelPrice(4.00, 0.40, 5.00, 20.00),
    # Conservative estimates use Gemini 3.8 Flash announced 2027 rates.
    "gemini-3.8-flash": ModelPrice(1.50, 0.15, 1.50, 7.50),
    "claude-sonnet-4-6": ModelPrice(3.00, 0.30, 6.00, 15.00),
}


@dataclass(frozen=True)
class CostRoute:
    model: str
    tier: str
    reasoning_effort: str
    max_output_tokens: int
    request_budget_usd: float
    image_detail: str = "low"
    pdf_detail: str = "low"


def model_price(model: str) -> ModelPrice | None:
    return MODEL_PRICES.get(model.strip().lower())


def estimate_model_cost(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float | None:
    price = model_price(model)
    if price is None:
        return None

    input_tokens = max(0, int(input_tokens))
    output_tokens = max(0, int(output_tokens))
    cached_input_tokens = max(0, min(int(cached_input_tokens), input_tokens))
    cache_write_tokens = max(
        0,
        min(int(cache_write_tokens), input_tokens - cached_input_tokens),
    )
    uncached_input_tokens = max(
        0,
        input_tokens - cached_input_tokens - cache_write_tokens,
    )
    long_context = input_tokens > 272_000
    input_multiplier = 2.0 if long_context else 1.0
    output_multiplier = 1.5 if long_context else 1.0
    return round(
        (uncached_input_tokens / 1_000_000)
        * price.input_per_million
        * input_multiplier
        + (cached_input_tokens / 1_000_000)
        * price.cached_input_per_million
        * input_multiplier
        + (cache_write_tokens / 1_000_000)
        * price.cache_write_per_million
        * input_multiplier
        + (output_tokens / 1_000_000)
        * price.output_per_million
        * output_multiplier,
        8,
    )


def _complexity_score(
    text: str,
    *,
    has_images: bool = False,
    has_files: bool = False,
    capabilities: Iterable[str] = (),
) -> int:
    lowered = text.casefold()
    score = 0
    if len(text) > 3000:
        score += 1
    if len(text) > 9000:
        score += 1
    if has_images or has_files:
        score += 1

    medium_terms = (
        "architecture",
        "build",
        "develop",
        "application",
        "software",
        "code",
        "repository",
        "website",
        "api",
        "debug",
        "refactor",
        "migration",
        "production",
        "security",
        "database",
        "deploy",
        "integration",
        "algorithm",
        "financial",
        "legal",
        "medical",
        "complex",
        "multi-step",
        "reasoning",
    )
    hard_terms = (
        "critical",
        "root cause",
        "incident",
        "vulnerability",
        "cryptography",
        "distributed system",
        "compiler",
        "kernel",
        "formal proof",
        "high stakes",
    )
    if any(term in lowered for term in medium_terms):
        score += 2
    if any(term in lowered for term in hard_terms):
        score += 2

    capability_set = {str(item).casefold() for item in capabilities}
    if capability_set & {"engineering", "architecture"}:
        score += 1
    if capability_set & {"security", "legal", "medical"}:
        score += 2
    return score


def choose_cost_route(
    settings: Settings,
    *,
    purpose: str,
    text: str = "",
    attempt: int = 0,
    has_images: bool = False,
    has_files: bool = False,
    capabilities: Iterable[str] = (),
    explicit_model: str | None = None,
) -> CostRoute:
    if not settings.ai_cost_governor_enabled:
        model = explicit_model or settings.model_default
        return CostRoute(
            model=model,
            tier="configured",
            reasoning_effort="medium",
            max_output_tokens=settings.model_max_output_tokens,
            request_budget_usd=settings.ai_request_max_usd,
            image_detail="auto",
            pdf_detail="auto",
        )

    economy = settings.model_economy
    balanced = settings.model_balanced
    premium = settings.model_premium

    if explicit_model:
        model = explicit_model
        tier = "explicit"
    elif purpose == "pdf":
        if attempt <= 1:
            model, tier = economy, "economy"
        else:
            model, tier = balanced, "balanced"
    elif purpose in {"planner", "validation", "background"}:
        model, tier = economy, "economy"
    else:
        score = _complexity_score(
            text,
            has_images=has_images,
            has_files=has_files,
            capabilities=capabilities,
        )
        if score <= 3:
            model, tier = economy, "economy"
        elif score <= 5:
            model, tier = balanced, "balanced"
        else:
            model, tier = premium, "premium"

    if purpose == "pdf":
        max_output = min(
            settings.ai_pdf_max_output_tokens,
            2200 if attempt == 0 else 1400,
        )
        budget = settings.ai_pdf_request_max_usd
    elif purpose == "planner":
        max_output = min(settings.model_max_output_tokens, 700)
        budget = min(settings.ai_request_max_usd, 0.015)
    else:
        max_output = settings.model_max_output_tokens
        budget = settings.ai_request_max_usd

    effort = "none"
    if tier == "balanced":
        effort = "low"
    elif tier in {"premium", "explicit"}:
        effort = "medium"

    return CostRoute(
        model=model,
        tier=tier,
        reasoning_effort=effort,
        max_output_tokens=max_output,
        request_budget_usd=budget,
        image_detail=settings.ai_image_detail,
        pdf_detail=settings.ai_pdf_detail,
    )


def apply_budget_pressure(
    settings: Settings,
    route: CostRoute,
    *,
    monthly_utilization: float,
) -> CostRoute:
    """Progressively reduce AI spend as the monthly envelope is consumed."""
    utilization = max(0.0, float(monthly_utilization))
    if utilization < settings.ai_spend_warning_ratio:
        return route

    model = route.model
    tier = route.tier
    effort = route.reasoning_effort
    max_output = route.max_output_tokens
    budget = route.request_budget_usd

    if utilization >= settings.ai_conservation_ratio:
        if tier != "explicit":
            model = settings.model_economy
            tier = "conservation"
            effort = "none"
        max_output = min(max_output, 600 if route.pdf_detail == "low" else 900)
        budget = min(budget, 0.02)
    else:
        if tier == "premium":
            model = settings.model_balanced
            tier = "balanced-conservation"
            effort = "low"
        max_output = min(max_output, 800)
        budget = min(budget, 0.03)

    return CostRoute(
        model=model,
        tier=tier,
        reasoning_effort=effort,
        max_output_tokens=max_output,
        request_budget_usd=budget,
        image_detail=route.image_detail,
        pdf_detail=route.pdf_detail,
    )
