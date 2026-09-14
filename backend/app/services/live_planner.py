import json
import re
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import settings
from backend.app.core.modeling import ModelGatewayError, ModelProvider, ModelRequest
from backend.app.core.orchestration import PlannedStep, build_default_plan
from backend.app.services.model_gateway import ModelGateway

_ALLOWED_CAPABILITIES = {
    "research",
    "analysis",
    "architecture",
    "engineering",
    "validation",
}


@dataclass(frozen=True)
class PlanResult:
    steps: list[PlannedStep]
    planner_version: str
    metadata: dict[str, Any]


def _json_payload(text: str) -> Any:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    return json.loads(stripped)


def _validate_steps(payload: Any) -> list[PlannedStep]:
    raw_steps = payload.get("steps") if isinstance(payload, dict) else None
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 8:
        raise ValueError("Planner must return between 1 and 8 steps")
    steps: list[PlannedStep] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise ValueError("Each step must be an object")
        title = str(raw.get("title", "")).strip()
        objective = str(raw.get("objective", "")).strip()
        capability = str(raw.get("capability", "")).strip().lower()
        if not title or not objective or capability not in _ALLOWED_CAPABILITIES:
            raise ValueError(f"Invalid planner step {index + 1}")
        priority = max(0, min(100, int(raw.get("priority", 10))))
        steps.append(PlannedStep(title[:200], objective, [capability], priority))
    return steps


def build_live_plan(
    objective: str,
    *,
    gateway: ModelGateway | None = None,
) -> PlanResult:
    try:
        provider = ModelProvider(settings.model_provider)
    except ValueError:
        provider = ModelProvider.MOCK
    if provider is ModelProvider.MOCK:
        return PlanResult(
            build_default_plan(objective),
            "deterministic-v1",
            {"mode": "fallback", "reason": "mock_provider"},
        )

    request = ModelRequest(
        provider=provider,
        model=settings.model_default,
        instructions=(
            "You are Seldrune's governed planning engine. Convert the owner's objective "
            "into the smallest sufficient sequence of executable steps. Obey explicit "
            "step-count and no-external-action constraints. Return JSON only in this form: "
            '{"steps":[{"title":"short title","objective":"specific outcome",'
            '"capability":"research|analysis|architecture|engineering|validation",'
            '"priority":30}]}. Use 1-8 steps. Do not claim work has already happened."
        ),
        input_text=f"Owner objective:\n{objective}",
        max_output_tokens=min(settings.model_max_output_tokens, 1200),
        metadata={"purpose": "owner_command_planning"},
    )
    try:
        result, latency_ms = (gateway or ModelGateway(settings)).generate(request)
        steps = _validate_steps(_json_payload(result.output_text))
        return PlanResult(
            steps,
            "live-model-v1",
            {
                "mode": "live",
                "provider": result.provider.value,
                "model": result.model,
                "response_id": result.response_id,
                "latency_ms": latency_ms,
                "usage": {
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "total_tokens": result.usage.total_tokens,
                },
            },
        )
    except (ModelGatewayError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return PlanResult(
            build_default_plan(objective),
            "deterministic-v1",
            {
                "mode": "fallback",
                "provider": provider.value,
                "model": settings.model_default,
                "reason": type(exc).__name__,
            },
        )
