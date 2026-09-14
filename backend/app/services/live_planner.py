import json
import re
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import settings
from backend.app.core.modeling import ModelGatewayError, ModelProvider, ModelRequest
from backend.app.core.orchestration import PlannedStep
from backend.app.services.model_gateway import ModelGateway

_ALLOWED_CAPABILITIES = (
    "research",
    "analysis",
    "architecture",
    "engineering",
    "validation",
)
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}
_FALLBACK_TEMPLATES = (
    ("Research the objective", "Collect reliable evidence and constraints for", "research", 80),
    ("Analyze findings", "Analyze evidence, risks, economics, and options for", "analysis", 70),
    ("Design the solution", "Design a practical governed approach for", "architecture", 60),
    ("Review safety and controls", "Define security and governance controls for", "architecture", 50),
    ("Implement the solution", "Build the approved solution for", "engineering", 40),
    ("Validate the solution", "Test correctness and acceptance criteria for", "validation", 30),
    ("Plan rollout", "Prepare a controlled rollout and recovery plan for", "architecture", 20),
    ("Measure outcomes", "Define success measures and review criteria for", "analysis", 10),
)


@dataclass(frozen=True)
class PlanResult:
    steps: list[PlannedStep]
    planner_version: str
    metadata: dict[str, Any]


def _explicit_step_count(objective: str) -> int | None:
    match = re.search(
        r"\b(?:exactly\s+)?(one|two|three|four|five|six|seven|eight|[1-8])"
        r"(?:[- ](?:step|steps)|\s+(?:planning\s+)?steps?)\b",
        objective.lower(),
    )
    if match is None:
        return None
    value = match.group(1)
    return int(value) if value.isdigit() else _NUMBER_WORDS[value]


def _fallback_plan(objective: str, count: int | None) -> list[PlannedStep]:
    step_count = count or (5 if any(
        term in objective.lower()
        for term in ("app", "automation", "build", "create", "software", "system")
    ) else 3)
    return [
        PlannedStep(title, f"{action}: {objective}", [capability], priority)
        for title, action, capability, priority in _FALLBACK_TEMPLATES[:step_count]
    ]


def _json_payload(text: str) -> Any:
    stripped = text.strip()
    fenced = re.search(r"\`\`\`(?:json)?\s*(.*?)\s*\`\`\`", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    elif not stripped.startswith("{"):
        start, end = stripped.find("{"), stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    return json.loads(stripped)


def _validate_steps(payload: Any, expected_count: int | None) -> list[PlannedStep]:
    raw_steps = payload.get("steps") if isinstance(payload, dict) else None
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= 8:
        raise ValueError("Planner must return between 1 and 8 steps")
    if expected_count is not None and len(raw_steps) != expected_count:
        raise ValueError(f"Planner did not return exactly {expected_count} steps")
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


def _plan_schema(expected_count: int | None) -> dict[str, Any]:
    minimum = expected_count or 1
    maximum = expected_count or 8
    return {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "minItems": minimum,
                "maxItems": maximum,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "objective": {"type": "string"},
                        "capability": {
                            "type": "string",
                            "enum": list(_ALLOWED_CAPABILITIES),
                        },
                        "priority": {"type": "integer", "minimum": 0, "maximum": 100},
                    },
                    "required": ["title", "objective", "capability", "priority"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["steps"],
        "additionalProperties": False,
    }


def build_live_plan(
    objective: str,
    *,
    gateway: ModelGateway | None = None,
) -> PlanResult:
    expected_count = _explicit_step_count(objective)
    try:
        provider = ModelProvider(settings.model_provider)
    except ValueError:
        provider = ModelProvider.MOCK
    if provider is ModelProvider.MOCK:
        return PlanResult(
            _fallback_plan(objective, expected_count),
            "deterministic-v2",
            {"mode": "fallback", "reason": "Mock provider is configured"},
        )

    request = ModelRequest(
        provider=provider,
        model=settings.model_default,
        instructions=(
            "You are Seldrune's governed planning engine. Convert the owner's objective "
            "into the smallest sufficient sequence of executable steps. Obey explicit "
            "step-count and no-external-action constraints. Do not claim work happened."
        ),
        input_text=f"Owner objective:\n{objective}",
        max_output_tokens=min(settings.model_max_output_tokens, 1200),
        metadata={"purpose": "owner_command_planning"},
        response_schema=_plan_schema(expected_count),
    )
    try:
        result, latency_ms = (gateway or ModelGateway(settings)).generate(request)
        steps = _validate_steps(_json_payload(result.output_text), expected_count)
        return PlanResult(
            steps,
            "live-model-v2",
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
    except (ModelGatewayError, ValueError, TypeError) as exc:
        return PlanResult(
            _fallback_plan(objective, expected_count),
            "deterministic-v2",
            {
                "mode": "fallback",
                "provider": provider.value,
                "model": settings.model_default,
                "reason": str(exc)[:160],
            },
        )
