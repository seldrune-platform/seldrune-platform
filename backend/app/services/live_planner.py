import json
import re
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import settings
from backend.app.core.modeling import ModelGatewayError, ModelProvider, ModelRequest
from backend.app.core.orchestration import PlannedStep
from backend.app.services.ai_cost_governor import choose_cost_route
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
    (
        "Review safety and controls",
        "Define security and governance controls for",
        "architecture",
        50,
    ),
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
    step_count = count or (
        5
        if any(
            term in objective.lower()
            for term in ("app", "automation", "build", "create", "software", "system")
        )
        else 3
    )
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


def _validate_steps(
    payload: Any,
    expected_count: int | None,
    *,
    allowed_tool_slugs: set[str] | None = None,
) -> list[PlannedStep]:
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
        tool_slug_value = raw.get("tool_slug")
        tool_slug = (
            str(tool_slug_value).strip()
            if isinstance(tool_slug_value, str) and tool_slug_value.strip()
            else None
        )
        if tool_slug is not None and tool_slug not in (allowed_tool_slugs or set()):
            raise ValueError(f"Planner selected unavailable tool: {tool_slug}")
        tool_input: dict[str, Any] | None = None
        if tool_slug is not None:
            raw_tool_input = raw.get("tool_input_json")
            if raw_tool_input in (None, ""):
                tool_input = {}
            elif not isinstance(raw_tool_input, str):
                raise ValueError("tool_input_json must be a JSON string")
            else:
                decoded_tool_input = json.loads(raw_tool_input)
                if not isinstance(decoded_tool_input, dict):
                    raise ValueError("tool_input_json must decode to an object")
                tool_input = decoded_tool_input
        steps.append(
            PlannedStep(
                title[:200],
                objective,
                [capability],
                priority,
                False,
                tool_slug,
                tool_input,
            )
        )
    return steps


def _plan_schema(
    expected_count: int | None,
    available_tool_slugs: set[str],
) -> dict[str, Any]:
    minimum = expected_count or 1
    maximum = expected_count or 8
    tool_values: list[str | None] = [None, *sorted(available_tool_slugs)]
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
                        "tool_slug": {
                            "type": ["string", "null"],
                            "enum": tool_values,
                        },
                        "tool_input_json": {"type": ["string", "null"]},
                    },
                    "required": [
                        "title",
                        "objective",
                        "capability",
                        "priority",
                        "tool_slug",
                        "tool_input_json",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["steps"],
        "additionalProperties": False,
    }


def _guidance_summary(guidance: dict[str, Any] | None) -> dict[str, Any]:
    if not guidance or not guidance.get("applied"):
        return {
            "applied": False,
            "sample_count": 0,
            "historical_success_rate": None,
            "confidence": 0.0,
            "preferred_capabilities": [],
            "caution_capabilities": [],
            "advisories": [],
            "adaptations": [],
        }
    return {
        "version": guidance.get("version"),
        "applied": True,
        "sample_count": int(guidance.get("sample_count") or 0),
        "reflection_sample_count": int(guidance.get("reflection_sample_count") or 0),
        "outcome_sample_count": int(guidance.get("outcome_sample_count") or 0),
        "historical_success_rate": guidance.get("historical_success_rate"),
        "confidence": guidance.get("confidence"),
        "preferred_capabilities": list(guidance.get("preferred_capabilities") or [])[:5],
        "caution_capabilities": list(guidance.get("caution_capabilities") or [])[:5],
        "recommendations": list(guidance.get("recommendations") or [])[:5],
        "recurring_cautions": list(guidance.get("recurring_cautions") or [])[:5],
        "advisories": list(guidance.get("advisories") or [])[:6],
        "adaptations": [],
    }


def _apply_adaptive_overlay(
    steps: list[PlannedStep],
    *,
    objective: str,
    expected_count: int | None,
    guidance: dict[str, Any] | None,
) -> tuple[list[PlannedStep], list[str]]:
    if not guidance or not guidance.get("applied"):
        return steps, []

    preferred = set(guidance.get("preferred_capabilities") or [])
    adapted: list[PlannedStep] = []
    priority_bumped = False
    for step in steps:
        capability = step.required_capabilities[0] if step.required_capabilities else ""
        bump = 5 if capability in preferred else 0
        if bump:
            priority_bumped = True
        adapted.append(
            PlannedStep(
                step.title,
                step.objective,
                list(step.required_capabilities),
                min(100, step.priority + bump),
                step.requires_approval,
                step.tool_slug,
                step.tool_input,
            )
        )

    adaptations: list[str] = []
    if priority_bumped:
        adaptations.append("preferred_capability_priority_boost")

    recommendations = set(guidance.get("recommendations") or [])
    recurring_cautions = set(guidance.get("recurring_cautions") or [])
    caution_capabilities = set(guidance.get("caution_capabilities") or [])
    success_rate = guidance.get("historical_success_rate")
    sample_count = int(guidance.get("sample_count") or 0)

    needs_research = "preserve_research_preflight_for_similar_work" in recommendations
    needs_validation = bool(
        "review_failed_capabilities_before_repeating_similar_work" in recommendations
        or "task_failures_were_observed" in recurring_cautions
        or "execution_encountered_blocked_steps" in recurring_cautions
        or caution_capabilities
        or (
            sample_count >= 2
            and isinstance(success_rate, (int, float))
            and success_rate < 0.5
        )
    )
    capabilities = {
        capability
        for step in adapted
        for capability in step.required_capabilities
    }

    if expected_count is None:
        if needs_research and "research" not in capabilities and len(adapted) < 8:
            adapted.insert(
                0,
                PlannedStep(
                    "Re-establish evidence",
                    f"Collect current evidence and constraints before proceeding with: {objective}",
                    ["research"],
                    85,
                ),
            )
            capabilities.add("research")
            adaptations.append("research_step_added_from_history")
        if needs_validation and "validation" not in capabilities and len(adapted) < 8:
            adapted.append(
                PlannedStep(
                    "Validate learned risks",
                    f"Validate historical failure risks and acceptance criteria for: {objective}",
                    ["validation"],
                    35,
                )
            )
            adaptations.append("validation_step_added_from_history")
    elif (needs_research and "research" not in capabilities) or (
        needs_validation and "validation" not in capabilities
    ):
        adaptations.append("owner_step_count_preserved_over_history")

    return adapted, adaptations


def _planner_input(
    objective: str,
    guidance: dict[str, Any] | None,
    available_tools: list[dict[str, Any]] | None,
) -> str:
    summary = _guidance_summary(guidance)
    tool_catalog = [
        {
            "slug": str(tool.get("slug") or ""),
            "description": str(tool.get("description") or ""),
            "provider": str(tool.get("provider") or ""),
            "action_name": str(tool.get("action_name") or ""),
            "risk_level": str(tool.get("risk_level") or ""),
            "input_schema": tool.get("input_schema") or {},
            "input_defaults": list(tool.get("input_defaults") or []),
        }
        for tool in (available_tools or [])
        if tool.get("slug")
    ]
    base = f"Owner objective:\n{objective}"
    if tool_catalog:
        base += (
            "\n\nAvailable registered tools. Use a tool only when the step must perform "
            "a real action. Set tool_slug to the exact slug and tool_input_json to a JSON "
            "object string matching the tool input schema. Fields listed in input_defaults "
            "are supplied by Seldrune at execution when omitted; never invent values for them. "
            "Otherwise set both fields to null."
            f"\n{json.dumps(tool_catalog, separators=(',', ':'))}"
        )
    if not summary["applied"]:
        return base
    bounded = {
        "sample_count": summary["sample_count"],
        "historical_success_rate": summary["historical_success_rate"],
        "confidence": summary["confidence"],
        "preferred_capabilities": summary["preferred_capabilities"],
        "caution_capabilities": summary["caution_capabilities"],
        "advisories": summary["advisories"],
    }
    return (
        f"{base}\n\n"
        "Seldrune learned planning guidance (advisory only; the owner's explicit constraints "
        f"always win):\n{json.dumps(bounded, separators=(',', ':'))}"
    )


def build_live_plan(
    objective: str,
    *,
    gateway: ModelGateway | None = None,
    adaptive_guidance: dict[str, Any] | None = None,
    available_tools: list[dict[str, Any]] | None = None,
) -> PlanResult:
    expected_count = _explicit_step_count(objective)
    guidance_metadata = _guidance_summary(adaptive_guidance)
    available_tool_slugs = {
        str(tool.get("slug"))
        for tool in (available_tools or [])
        if tool.get("slug")
    }
    try:
        provider = ModelProvider(settings.model_provider)
    except ValueError:
        provider = ModelProvider.MOCK
    if provider is ModelProvider.MOCK:
        steps, adaptations = _apply_adaptive_overlay(
            _fallback_plan(objective, expected_count),
            objective=objective,
            expected_count=expected_count,
            guidance=adaptive_guidance,
        )
        guidance_metadata["adaptations"] = adaptations
        return PlanResult(
            steps,
            "deterministic-v3-adaptive",
            {
                "mode": "fallback",
                "reason": "Mock provider is configured",
                "adaptive_planning": guidance_metadata,
                "available_tool_count": len(available_tool_slugs),
                "tool_steps": sum(bool(step.tool_slug) for step in steps),
            },
        )

    route = choose_cost_route(
        settings,
        purpose="planner",
        text=objective,
    )
    request = ModelRequest(
        provider=provider,
        model=route.model,
        instructions=(
            "You are Seldrune's governed planning engine. Convert the owner's objective "
            "into the smallest sufficient sequence of executable steps. Obey explicit "
            "step-count and no-external-action constraints. When a real external or internal "
            "action is required and an appropriate registered tool is listed, select that "
            "tool instead of merely describing the action. Never invent tool names. "
            "Seldrune may provide bounded learned guidance from prior outcomes; use it only "
            "when relevant and never let it override the owner's explicit instruction. "
            "Do not claim work happened."
        ),
        input_text=_planner_input(objective, adaptive_guidance, available_tools),
        max_output_tokens=route.max_output_tokens,
        metadata={
            "purpose": "owner_command_planning",
            "adaptive_planning": bool(guidance_metadata["applied"]),
        },
        response_schema=_plan_schema(expected_count, available_tool_slugs),
        reasoning_effort=route.reasoning_effort,
        prompt_cache_key="seldrune:owner-command-planner",
        max_estimated_cost_usd=route.request_budget_usd,
        exact_token_preflight=False,
    )
    try:
        result, latency_ms = (gateway or ModelGateway(settings)).generate(request)
        steps = _validate_steps(
            _json_payload(result.output_text),
            expected_count,
            allowed_tool_slugs=available_tool_slugs,
        )
        steps, adaptations = _apply_adaptive_overlay(
            steps,
            objective=objective,
            expected_count=expected_count,
            guidance=adaptive_guidance,
        )
        guidance_metadata["adaptations"] = adaptations
        return PlanResult(
            steps,
            "live-model-v3-adaptive",
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
                "adaptive_planning": guidance_metadata,
            },
        )
    except (ModelGatewayError, ValueError, TypeError) as exc:
        steps, adaptations = _apply_adaptive_overlay(
            _fallback_plan(objective, expected_count),
            objective=objective,
            expected_count=expected_count,
            guidance=adaptive_guidance,
        )
        guidance_metadata["adaptations"] = adaptations
        return PlanResult(
            steps,
            "deterministic-v3-adaptive",
            {
                "mode": "fallback",
                "provider": provider.value,
                "model": route.model,
                "reason": str(exc)[:160],
                "adaptive_planning": guidance_metadata,
            },
        )
