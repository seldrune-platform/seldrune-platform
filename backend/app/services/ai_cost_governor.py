from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from threading import Lock
from time import monotonic

from backend.app.core.config import Settings
from backend.app.core.modeling import ModelRequest, ModelResult


_MODEL_RATES_USD_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (4.00, 20.00),
}


@dataclass(frozen=True)
class CostDecision:
    request: ModelRequest
    tier: str
    routed_from_model: str | None
    request_budget_usd: float
    scope: str | None
    scope_budget_usd: float | None


@dataclass
class _CacheEntry:
    result: ModelResult
    expires_at: float


_cache: dict[str, _CacheEntry] = {}
_scope_spend: dict[str, float] = {}
_lock = Lock()


def model_rates(model: str) -> tuple[float, float] | None:
    return _MODEL_RATES_USD_PER_MILLION.get(model)


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    rates = model_rates(model)
    if rates is None:
        return None
    input_rate, output_rate = rates
    return round(
        (max(0, input_tokens) / 1_000_000) * input_rate
        + (max(0, output_tokens) / 1_000_000) * output_rate,
        8,
    )


def _tier_from_request(settings: Settings, request: ModelRequest) -> str:
    explicit = str(request.metadata.get("cost_tier") or "").strip().lower()
    if explicit in {"economy", "balanced", "premium"}:
        return explicit
    if request.metadata.get("quality_critical") is True:
        return "premium"
    if request.metadata.get("cost_sensitive") is True:
        return "economy"

    output_limit = int(request.max_output_tokens or settings.model_max_output_tokens)
    if request.response_schema is not None:
        return "economy"
    if request.input_images or request.input_files:
        return "economy"
    if output_limit <= 2200:
        return settings.ai_default_tier
    if output_limit <= 6000:
        return "balanced"
    return "premium"


def govern_request(settings: Settings, request: ModelRequest) -> CostDecision:
    if not settings.ai_cost_governor_enabled or request.provider.value != "openai":
        return CostDecision(
            request=request,
            tier="unmanaged",
            routed_from_model=None,
            request_budget_usd=float(
                request.metadata.get(
                    "max_request_cost_usd",
                    settings.ai_max_request_cost_usd,
                )
            ),
            scope=None,
            scope_budget_usd=None,
        )

    tier = _tier_from_request(settings, request)
    model_by_tier = {
        "economy": settings.ai_economy_model,
        "balanced": settings.ai_balanced_model,
        "premium": settings.ai_premium_model,
    }
    output_by_tier = {
        "economy": settings.ai_economy_max_output_tokens,
        "balanced": settings.ai_balanced_max_output_tokens,
        "premium": settings.ai_premium_max_output_tokens,
    }

    chosen_model = model_by_tier[tier]
    requested_output = int(request.max_output_tokens or settings.model_max_output_tokens)
    capped_output = min(requested_output, output_by_tier[tier])
    routed_from = request.model if chosen_model != request.model else None

    governed = replace(
        request,
        model=chosen_model,
        max_output_tokens=capped_output,
    )
    request_budget = float(
        request.metadata.get(
            "max_request_cost_usd",
            settings.ai_max_request_cost_usd,
        )
    )
    scope_value = request.metadata.get("cost_scope")
    scope = str(scope_value).strip() if scope_value else None
    scope_budget = (
        float(
            request.metadata.get(
                "scope_budget_usd",
                settings.ai_default_scope_budget_usd,
            )
        )
        if scope
        else None
    )
    return CostDecision(
        request=governed,
        tier=tier,
        routed_from_model=routed_from,
        request_budget_usd=request_budget,
        scope=scope,
        scope_budget_usd=scope_budget,
    )


def projected_cost_exceeds_budget(
    decision: CostDecision,
    *,
    input_tokens: int,
) -> tuple[bool, float | None, str | None]:
    output_limit = int(decision.request.max_output_tokens or 0)
    projected = estimate_cost_usd(
        decision.request.model,
        input_tokens=input_tokens,
        output_tokens=output_limit,
    )
    if projected is None:
        return False, None, None

    if projected > decision.request_budget_usd:
        return (
            True,
            projected,
            (
                f"Projected AI request cost $\{projected:.4f} exceeds the "
                f"$\{decision.request_budget_usd:.4f} per-request budget"
            ),
        )

    if decision.scope and decision.scope_budget_usd is not None:
        with _lock:
            spent = _scope_spend.get(decision.scope, 0.0)
        if spent + projected > decision.scope_budget_usd:
            return (
                True,
                projected,
                (
                    f"Projected AI scope cost $\{spent + projected:.4f} exceeds the "
                    f"$\{decision.scope_budget_usd:.4f} budget"
                ),
            )
    return False, projected, None


def record_spend(decision: CostDecision, amount_usd: float | None) -> None:
    if amount_usd is None or amount_usd < 0 or not decision.scope:
        return
    with _lock:
        _scope_spend[decision.scope] = round(
            _scope_spend.get(decision.scope, 0.0) + amount_usd,
            8,
        )


def scope_spend(scope: str) -> float:
    with _lock:
        return _scope_spend.get(scope, 0.0)


def cache_key(request: ModelRequest) -> str:
    digest = sha256()
    digest.update(request.provider.value.encode())
    digest.update(request.model.encode())
    digest.update((request.instructions or "").encode())
    digest.update(request.input_text.encode())
    digest.update(str(request.max_output_tokens).encode())
    digest.update(repr(request.response_schema).encode())
    for image in request.input_images:
        digest.update(image.media_type.encode())
        digest.update(sha256(image.data_base64.encode()).digest())
    for file_input in request.input_files:
        digest.update((file_input.media_type or "").encode())
        digest.update(file_input.filename.encode())
        digest.update(sha256(file_input.data_base64.encode()).digest())
    return digest.hexdigest()


def should_cache(request: ModelRequest) -> bool:
    if request.metadata.get("cacheable") is False:
        return False
    if request.metadata.get("cacheable") is True:
        return True
    return request.response_schema is not None


def get_cached_result(
    settings: Settings,
    request: ModelRequest,
) -> ModelResult | None:
    if settings.ai_cache_ttl_seconds <= 0 or not should_cache(request):
        return None
    key = cache_key(request)
    now = monotonic()
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            _cache.pop(key, None)
            return None
        result = entry.result
    return replace(result, cache_hit=True, estimated_cost_usd=0.0)


def put_cached_result(
    settings: Settings,
    request: ModelRequest,
    result: ModelResult,
) -> None:
    if settings.ai_cache_ttl_seconds <= 0 or not should_cache(request):
        return
    key = cache_key(request)
    with _lock:
        _cache[key] = _CacheEntry(
            result=result,
            expires_at=monotonic() + settings.ai_cache_ttl_seconds,
        )


def external_operation_allowed(
    settings: Settings,
    *,
    estimated_cost_usd: float,
    budget_usd: float | None = None,
) -> tuple[bool, str | None]:
    limit = (
        float(budget_usd)
        if budget_usd is not None
        else settings.ai_default_scope_budget_usd
    )
    if estimated_cost_usd <= limit:
        return True, None
    return (
        False,
        (
            f"Estimated external AI operation cost $\{estimated_cost_usd:.4f} "
            f"exceeds the $\{limit:.4f} budget"
        ),
    )
