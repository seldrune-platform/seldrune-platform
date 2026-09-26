import base64
import binascii
import hashlib
from contextlib import suppress
from time import perf_counter
from typing import Any

from openai import OpenAI

from backend.app.core.config import Settings
from backend.app.core.modeling import (
    ModelGatewayError,
    ModelProvider,
    ModelProviderCapabilities,
    ModelRequest,
    ModelResult,
    ModelRouteCandidate,
    ModelRouteDecision,
    ModelRoutePerformanceEvidence,
    ModelRoutePerformanceSummary,
    ModelUsage,
)
from backend.app.services.ai_cost_governor import estimate_model_cost


PROMPT_CACHE_KEY_MAX_LENGTH = 64
RECENT_PERFORMANCE_WINDOW_SECONDS = 7 * 24 * 60 * 60
RECENT_PERFORMANCE_MIN_SAMPLES = 2
RECENT_PERFORMANCE_WEIGHT = 0.80
RECENT_DRIFT_THRESHOLD = 0.25


def model_route_performance_summary(
    candidate: ModelRouteCandidate,
    evidence: tuple[ModelRoutePerformanceEvidence, ...],
    *,
    recent_window_seconds: int,
    min_recent_samples: int,
) -> ModelRoutePerformanceSummary:
    if recent_window_seconds <= 0:
        raise ModelGatewayError("Recent performance window must be positive")
    if min_recent_samples <= 0:
        raise ModelGatewayError("Recent performance sample floor must be positive")

    deduped: dict[str, ModelRoutePerformanceEvidence] = {}
    for item in evidence:
        if item.provider is not candidate.provider or item.model != candidate.model:
            continue
        if not item.verified or not item.evidence_key.strip() or not item.evidence_refs:
            continue
        if item.age_seconds < 0:
            raise ModelGatewayError("Model performance evidence age cannot be negative")
        deduped.setdefault(item.evidence_key, item)

    history = tuple(deduped.values())
    if not history:
        return ModelRoutePerformanceSummary()

    lifetime_success_rate = sum(item.succeeded for item in history) / len(history)
    recent = tuple(
        item for item in history if item.age_seconds <= recent_window_seconds
    )
    if recent:
        weights = tuple(
            1.0 / (1.0 + (item.age_seconds / 86_400.0))
            for item in recent
        )
        weight_total = sum(weights)
        recent_success_rate = sum(
            weight * float(item.succeeded)
            for item, weight in zip(recent, weights, strict=True)
        ) / weight_total
    else:
        recent_success_rate = None

    trust_score: float | None = None
    if len(recent) >= min_recent_samples and recent_success_rate is not None:
        trust_score = (
            RECENT_PERFORMANCE_WEIGHT * recent_success_rate
            + (1.0 - RECENT_PERFORMANCE_WEIGHT) * lifetime_success_rate
        )

    drift_detected = bool(
        recent_success_rate is not None
        and len(history) > len(recent)
        and abs(recent_success_rate - lifetime_success_rate)
        >= RECENT_DRIFT_THRESHOLD
    )
    refs = tuple(
        dict.fromkeys(
            ref
            for item in recent
            for ref in item.evidence_refs
            if ref
        )
    )
    return ModelRoutePerformanceSummary(
        recent_verified_samples=len(recent),
        lifetime_verified_samples=len(history),
        recent_success_rate=(
            round(recent_success_rate, 6)
            if recent_success_rate is not None
            else None
        ),
        lifetime_success_rate=round(lifetime_success_rate, 6),
        trust_score=round(trust_score, 6) if trust_score is not None else None,
        drift_detected=drift_detected,
        evidence_refs=refs,
    )


def _rank_model_candidates(
    candidates: tuple[ModelRouteCandidate, ...],
    evidence: tuple[ModelRoutePerformanceEvidence, ...],
    *,
    recent_window_seconds: int,
    min_recent_samples: int,
) -> list[tuple[int, ModelRouteCandidate, ModelRoutePerformanceSummary]]:
    scored = [
        (
            index,
            candidate,
            model_route_performance_summary(
                candidate,
                evidence,
                recent_window_seconds=recent_window_seconds,
                min_recent_samples=min_recent_samples,
            ),
        )
        for index, candidate in enumerate(candidates)
    ]
    if not any(summary.trust_score is not None for _, _, summary in scored):
        return sorted(scored, key=lambda item: (item[1].priority, item[0]))

    return sorted(
        scored,
        key=lambda item: (
            -(
                item[2].trust_score
                if item[2].trust_score is not None
                else 0.5
            ),
            item[1].priority,
            item[0],
        ),
    )


def normalize_prompt_cache_key(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) <= PROMPT_CACHE_KEY_MAX_LENGTH:
        return cleaned
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]
    prefix_length = PROMPT_CACHE_KEY_MAX_LENGTH - len(digest) - 1
    prefix = cleaned[:prefix_length].rstrip(":-_")
    return f"{prefix}:{digest}"


def _is_prompt_cache_error(exc: Exception) -> bool:
    message = " ".join(str(exc).casefold().split())
    return (
        "prompt_cache_key" in message
        or "prompt cache key" in message
        or "prompt_cache_options" in message
        or "prompt cache options" in message
    )


_PROVIDER_CAPABILITIES: dict[ModelProvider, ModelProviderCapabilities] = {
    ModelProvider.MOCK: ModelProviderCapabilities(text=True),
    ModelProvider.OPENAI: ModelProviderCapabilities(
        text=True,
        structured_output=True,
        images=True,
        files=True,
        reasoning=True,
    ),
    ModelProvider.OPENAI_COMPATIBLE: ModelProviderCapabilities(
        text=True,
        structured_output=True,
    ),
}


def model_provider_capabilities(
    provider: ModelProvider,
) -> ModelProviderCapabilities:
    try:
        return _PROVIDER_CAPABILITIES[provider]
    except KeyError as exc:
        raise ModelGatewayError(f"Unsupported model provider: {provider}") from exc


class ModelGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(
        self,
        candidates: tuple[ModelRouteCandidate, ...],
        *,
        required_capabilities: tuple[str, ...] = ("text",),
        allowed_providers: tuple[ModelProvider, ...] | None = None,
        performance_evidence: tuple[ModelRoutePerformanceEvidence, ...] = (),
        recent_window_seconds: int = RECENT_PERFORMANCE_WINDOW_SECONDS,
        min_recent_samples: int = RECENT_PERFORMANCE_MIN_SAMPLES,
    ) -> ModelRouteDecision:
        if not candidates:
            raise ModelGatewayError("No model route candidates were provided")
        allowed = set(allowed_providers) if allowed_providers is not None else None
        required = tuple(dict.fromkeys(required_capabilities or ("text",)))
        ranked = _rank_model_candidates(
            candidates,
            performance_evidence,
            recent_window_seconds=recent_window_seconds,
            min_recent_samples=min_recent_samples,
        )
        for _index, candidate, performance in ranked:
            if allowed is not None and candidate.provider not in allowed:
                continue
            capabilities = model_provider_capabilities(candidate.provider)
            try:
                supported = capabilities.supports(required)
            except ValueError as exc:
                raise ModelGatewayError(str(exc)) from exc
            if supported:
                return ModelRouteDecision(
                    provider=candidate.provider,
                    model=candidate.model,
                    capabilities=capabilities,
                    required_capabilities=required,
                    performance=performance,
                )
        requirements = ", ".join(required)
        raise ModelGatewayError(
            f"No allowed model route satisfies required capabilities: {requirements}"
        )

    def generate(self, request: ModelRequest) -> tuple[ModelResult, int]:
        started = perf_counter()
        adapters = {
            ModelProvider.MOCK: self._generate_mock,
            ModelProvider.OPENAI: self._generate_openai,
            ModelProvider.OPENAI_COMPATIBLE: self._generate_openai_compatible,
        }
        adapter = adapters.get(request.provider)
        if adapter is None:
            raise ModelGatewayError(f"Unsupported model provider: {request.provider}")
        result = adapter(request)
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        return result, latency_ms

    def _generate_mock(self, request: ModelRequest) -> ModelResult:
        input_tokens = max(1, len(request.input_text.split()))
        output = f"Mock execution completed. {request.input_text[:500]}"
        output_tokens = max(1, len(output.split()))
        return ModelResult(
            provider=ModelProvider.MOCK,
            model=request.model,
            output_text=output,
            response_id="mock-response",
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )

    @staticmethod
    def _rough_input_token_estimate(
        request: ModelRequest,
        decoded_file_bytes: int,
    ) -> int:
        text_chars = len(request.input_text) + len(request.instructions or "")
        text_tokens = max(1, (text_chars + 3) // 4)
        image_tokens = 1200 * len(request.input_images)
        # Exact multimodal counting is preferred. This intentionally conservative
        # fallback protects the budget if token-count preflight is unavailable.
        file_tokens = max(0, decoded_file_bytes // 3)
        return text_tokens + image_tokens + file_tokens

    def _guard_request_cost(
        self,
        request: ModelRequest,
        *,
        input_tokens: int,
    ) -> None:
        budget = request.max_estimated_cost_usd
        if budget is None:
            return
        max_output_tokens = max(0, int(request.max_output_tokens or 0))
        worst_case = estimate_model_cost(
            request.model,
            input_tokens=input_tokens,
            output_tokens=max_output_tokens,
        )
        if worst_case is None:
            return
        if worst_case > budget:
            raise ModelGatewayError(
                "AI cost governor blocked request before generation: "
                f"estimated maximum USD {worst_case:.4f} exceeds "
                f"USD {budget:.4f} request budget"
            )

    def _generate_openai_compatible(self, request: ModelRequest) -> ModelResult:
        if not request.model or request.model.startswith("mock-"):
            raise ModelGatewayError("An OpenAI-compatible model must be configured")
        base_url = (self.settings.model_compatible_base_url or "").strip()
        if not base_url:
            raise ModelGatewayError(
                "SELDRUNE_MODEL_COMPATIBLE_BASE_URL must be configured"
            )
        unsupported: list[str] = []
        if request.input_images:
            unsupported.append("images")
        if request.input_files:
            unsupported.append("files")
        if request.reasoning_effort:
            unsupported.append("reasoning")
        if unsupported:
            raise ModelGatewayError(
                "OpenAI-compatible provider does not support requested capabilities: "
                + ", ".join(unsupported)
            )

        rough_tokens = self._rough_input_token_estimate(request, 0)
        self._guard_request_cost(request, input_tokens=rough_tokens)
        client = OpenAI(
            api_key=self.settings.model_compatible_api_key or "not-required",
            base_url=base_url,
            timeout=self.settings.model_timeout_seconds,
        )
        messages: list[dict[str, str]] = []
        if request.instructions:
            messages.append({"role": "system", "content": request.instructions})
        messages.append({"role": "user", "content": request.input_text})
        args: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }
        if request.max_output_tokens is not None:
            args["max_tokens"] = request.max_output_tokens
        if request.response_schema is not None:
            args["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "seldrune_response",
                    "strict": True,
                    "schema": request.response_schema,
                },
            }
        try:
            response = client.chat.completions.create(**args)
        except Exception as exc:
            detail = " ".join(str(exc).split())
            if len(detail) > 500:
                detail = detail[:497] + "..."
            suffix = f": {detail}" if detail else ""
            raise ModelGatewayError(
                f"OpenAI-compatible request failed ({type(exc).__name__}){suffix}"
            ) from exc

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_tokens", input_tokens + output_tokens) or 0
        )
        choices = getattr(response, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        output_text = getattr(message, "content", "") or ""
        estimated_cost = estimate_model_cost(
            request.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ModelResult(
            provider=ModelProvider.OPENAI_COMPATIBLE,
            model=request.model,
            output_text=output_text,
            response_id=getattr(response, "id", None),
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
            ),
        )

    def _generate_openai(self, request: ModelRequest) -> ModelResult:
        if not request.model or request.model.startswith("mock-"):
            raise ModelGatewayError("An OpenAI model must be configured")

        client = OpenAI(timeout=self.settings.model_timeout_seconds)
        uploaded_file_ids: list[str] = []
        decoded_file_bytes = 0
        try:
            model_input: Any = request.input_text
            if request.input_images or request.input_files:
                # Reusable heavy inputs come before the changing instruction text
                # so repeated work can reuse a larger cached prompt prefix.
                content: list[dict[str, Any]] = []
                for file_input in request.input_files:
                    try:
                        file_bytes = base64.b64decode(
                            file_input.data_base64,
                            validate=True,
                        )
                    except (ValueError, binascii.Error) as exc:
                        raise ModelGatewayError(
                            f"Invalid base64 content for {file_input.filename}"
                        ) from exc
                    decoded_file_bytes += len(file_bytes)
                    uploaded = client.files.create(
                        file=(
                            file_input.filename,
                            file_bytes,
                            file_input.media_type or "application/octet-stream",
                        ),
                        purpose="user_data",
                    )
                    uploaded_file_ids.append(uploaded.id)
                    item: dict[str, Any] = {
                        "type": "input_file",
                        "file_id": uploaded.id,
                    }
                    if (file_input.media_type or "").lower() == "application/pdf":
                        item["detail"] = request.pdf_detail
                    content.append(item)

                for image in request.input_images:
                    content.append(
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{image.media_type};base64,{image.data_base64}"
                            ),
                            "detail": request.image_detail,
                        }
                    )

                content.append({"type": "input_text", "text": request.input_text})
                model_input = [{"role": "user", "content": content}]

            response_args: dict[str, Any] = {
                "model": request.model,
                "input": model_input,
                "instructions": request.instructions,
                "max_output_tokens": request.max_output_tokens,
            }
            if request.response_schema is not None:
                response_args["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "seldrune_response",
                        "strict": True,
                        "schema": request.response_schema,
                    }
                }
            if request.reasoning_effort and request.model.startswith("gpt-5.6"):
                response_args["reasoning"] = {
                    "effort": request.reasoning_effort,
                }
            if (
                self.settings.ai_prompt_cache_enabled
                and request.prompt_cache_key
            ):
                response_args["prompt_cache_key"] = normalize_prompt_cache_key(
                    request.prompt_cache_key
                )
                if request.model.startswith("gpt-5.6"):
                    response_args["prompt_cache_options"] = {"ttl": "30m"}

            if request.max_estimated_cost_usd is not None:
                preflight_tokens: int | None = None
                if (
                    request.exact_token_preflight
                    and self.settings.ai_exact_token_preflight
                ):
                    try:
                        count = client.responses.input_tokens.count(
                            model=request.model,
                            input=model_input,
                            instructions=request.instructions,
                        )
                        preflight_tokens = int(
                            getattr(count, "input_tokens", 0) or 0
                        )
                    except Exception:
                        preflight_tokens = None

                if not preflight_tokens:
                    preflight_tokens = self._rough_input_token_estimate(
                        request,
                        decoded_file_bytes,
                    )
                self._guard_request_cost(
                    request,
                    input_tokens=preflight_tokens,
                )

            try:
                response = client.responses.create(**response_args)
            except Exception as exc:
                if (
                    "prompt_cache_key" in response_args
                    and _is_prompt_cache_error(exc)
                ):
                    retry_args = dict(response_args)
                    retry_args.pop("prompt_cache_key", None)
                    retry_args.pop("prompt_cache_options", None)
                    response = client.responses.create(**retry_args)
                else:
                    raise
        except ModelGatewayError:
            raise
        except Exception as exc:
            detail = " ".join(str(exc).split())
            if len(detail) > 500:
                detail = detail[:497] + "..."
            suffix = f": {detail}" if detail else ""
            raise ModelGatewayError(
                f"OpenAI request failed ({type(exc).__name__}){suffix}"
            ) from exc
        finally:
            for file_id in uploaded_file_ids:
                with suppress(Exception):
                    client.files.delete(file_id)

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_tokens", input_tokens + output_tokens) or 0
        )
        input_details = getattr(usage, "input_tokens_details", None)
        cached_input_tokens = int(
            getattr(input_details, "cached_tokens", 0) or 0
        )
        cache_write_tokens = int(
            getattr(input_details, "cache_write_tokens", 0) or 0
        )
        estimated_cost = estimate_model_cost(
            request.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_tokens=cache_write_tokens,
        )

        return ModelResult(
            provider=ModelProvider.OPENAI,
            model=request.model,
            output_text=getattr(response, "output_text", "") or "",
            response_id=getattr(response, "id", None),
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cached_input_tokens=cached_input_tokens,
                cache_write_tokens=cache_write_tokens,
                estimated_cost_usd=estimated_cost,
            ),
        )
