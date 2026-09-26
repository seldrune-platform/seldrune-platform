from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.app.core.modeling import (
    ModelGatewayError,
    ModelProvider,
    ModelRouteCandidate,
    ModelRoutePerformanceEvidence,
)
from backend.app.services.ai_cost_governor import estimate_model_cost
from backend.app.services.model_gateway import (
    RECENT_PERFORMANCE_MIN_SAMPLES,
    RECENT_PERFORMANCE_WINDOW_SECONDS,
    model_provider_capabilities,
    model_route_performance_summary,
)


@dataclass(frozen=True)
class CostAwareModelCandidate:
    provider: ModelProvider
    model: str
    priority: int = 100
    verification_reserve_usd: float = 0.0
    generation_cost_override_usd: float | None = None


@dataclass(frozen=True)
class CostAwareModelDecision:
    provider: ModelProvider
    model: str
    generation_cost_usd: float
    verification_reserve_usd: float
    projected_total_cost_usd: float
    trust_score: float
    projected_risk: float
    recent_verified_samples: int
    evidence_refs: tuple[str, ...]
    required_capabilities: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def select_cost_aware_model_route(
    *,
    candidates: tuple[CostAwareModelCandidate, ...],
    performance_evidence: tuple[ModelRoutePerformanceEvidence, ...],
    required_capabilities: tuple[str, ...],
    projected_input_tokens: int,
    projected_output_tokens: int,
    max_total_cost_usd: float,
    minimum_trust: float = 0.75,
    max_projected_risk: float = 0.25,
    recent_window_seconds: int = RECENT_PERFORMANCE_WINDOW_SECONDS,
    min_recent_samples: int = RECENT_PERFORMANCE_MIN_SAMPLES,
    allowed_providers: tuple[ModelProvider, ...] | None = None,
) -> CostAwareModelDecision:
    """
    Choose the cheapest verified model path inside quality and risk limits.

    Cost includes both projected generation spend and an explicit reserve for
    independent verification. Only provenance-backed recency trust from the
    existing model router is accepted as quality evidence.
    """
    if not candidates:
        raise ModelGatewayError("No cost-aware model candidates were provided")
    if projected_input_tokens < 0 or projected_output_tokens < 0:
        raise ModelGatewayError("Projected token counts cannot be negative")
    if max_total_cost_usd < 0:
        raise ModelGatewayError("Maximum route cost cannot be negative")
    if not 0.0 <= minimum_trust <= 1.0:
        raise ModelGatewayError("Minimum trust must be within 0..1")
    if not 0.0 <= max_projected_risk <= 1.0:
        raise ModelGatewayError("Maximum projected risk must be within 0..1")

    required = tuple(dict.fromkeys(required_capabilities or ("text",)))
    allowed = set(allowed_providers) if allowed_providers is not None else None
    eligible: list[
        tuple[
            float,
            float,
            int,
            int,
            CostAwareModelCandidate,
            object,
            float,
        ]
    ] = []

    for index, candidate in enumerate(candidates):
        if allowed is not None and candidate.provider not in allowed:
            continue
        if candidate.verification_reserve_usd < 0:
            raise ModelGatewayError("Verification reserve cannot be negative")
        if (
            candidate.generation_cost_override_usd is not None
            and candidate.generation_cost_override_usd < 0
        ):
            raise ModelGatewayError(
                "Generation cost override cannot be negative"
            )

        capabilities = model_provider_capabilities(candidate.provider)
        try:
            supported = capabilities.supports(required)
        except ValueError as exc:
            raise ModelGatewayError(str(exc)) from exc
        if not supported:
            continue

        route_candidate = ModelRouteCandidate(
            provider=candidate.provider,
            model=candidate.model,
            priority=candidate.priority,
        )
        performance = model_route_performance_summary(
            route_candidate,
            performance_evidence,
            recent_window_seconds=recent_window_seconds,
            min_recent_samples=min_recent_samples,
        )
        trust = performance.trust_score
        if trust is None or not performance.evidence_refs:
            continue
        projected_risk = max(0.0, min(1.0, 1.0 - trust))
        if trust < minimum_trust or projected_risk > max_projected_risk:
            continue

        generation_cost = candidate.generation_cost_override_usd
        if generation_cost is None:
            generation_cost = estimate_model_cost(
                candidate.model,
                input_tokens=projected_input_tokens,
                output_tokens=projected_output_tokens,
            )
        if generation_cost is None:
            continue

        total_cost = generation_cost + candidate.verification_reserve_usd
        if total_cost > max_total_cost_usd + 1e-12:
            continue

        eligible.append(
            (
                round(total_cost, 8),
                -trust,
                candidate.priority,
                index,
                candidate,
                performance,
                round(generation_cost, 8),
            )
        )

    if not eligible:
        raise ModelGatewayError(
            "No verified model route satisfies capability, quality, risk, "
            "and total-cost constraints"
        )

    eligible.sort(key=lambda item: item[:4])
    total_cost, negative_trust, _priority, _index, candidate, performance, generation_cost = (
        eligible[0]
    )
    trust = -negative_trust
    return CostAwareModelDecision(
        provider=candidate.provider,
        model=candidate.model,
        generation_cost_usd=generation_cost,
        verification_reserve_usd=round(candidate.verification_reserve_usd, 8),
        projected_total_cost_usd=total_cost,
        trust_score=round(trust, 6),
        projected_risk=round(1.0 - trust, 6),
        recent_verified_samples=performance.recent_verified_samples,
        evidence_refs=performance.evidence_refs,
        required_capabilities=required,
    )
