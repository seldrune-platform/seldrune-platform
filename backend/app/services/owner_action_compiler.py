from __future__ import annotations

import re
from typing import Any

from backend.app.core.orchestration import PlannedStep

_TOOL_INTENTS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "gmail",
        "send-message",
        re.compile(
            r"\b(send|notify|email|mail)\b.{0,80}"
            r"\b(email|mail|gmail|owner|recipient|client|customer|team)\b",
            re.I,
        ),
    ),
    (
        "github",
        "create-issue",
        re.compile(r"\b(create|open|file)\b.{0,80}\b(issue|bug)\b", re.I),
    ),
    (
        "github",
        "comment",
        re.compile(
            r"\b(comment|reply)\b.{0,80}\b(issue|pull request|pr)\b",
            re.I,
        ),
    ),
    (
        "github",
        "create-pull-request",
        re.compile(r"\b(create|open)\b.{0,80}\b(pull request|pr)\b", re.I),
    ),
    (
        "github",
        "merge-pull-request",
        re.compile(
            r"\bmerge\b.{0,80}\b(pull request|pr)\b"
            r"|\b(pull request|pr)\b.{0,80}\bmerge\b",
            re.I,
        ),
    ),
    (
        "github",
        "dispatch-workflow",
        re.compile(
            r"\b(dispatch|trigger|run)\b.{0,80}\b(workflow|github action)\b",
            re.I,
        ),
    ),
)


def required_external_tool_actions(order: str) -> list[tuple[str, str]]:
    located: list[tuple[int, str, str]] = []
    for provider, action_name, pattern in _TOOL_INTENTS:
        match = pattern.search(order)
        if match is not None:
            located.append((match.start(), provider, action_name))

    deploy_match = re.search(r"\b(deploy|redeploy)\b", order, re.I)
    github_workflow = re.search(r"\b(workflow|github action)\b", order, re.I)
    if deploy_match is not None and github_workflow is None:
        located.append((deploy_match.start(), "render", "deploy-service"))

    deduped: dict[tuple[str, str], int] = {}
    for position, provider, action_name in located:
        key = (provider, action_name)
        deduped[key] = min(position, deduped.get(key, position))
    return [
        key
        for key, _position in sorted(
            deduped.items(),
            key=lambda item: (item[1], item[0][0], item[0][1]),
        )
    ]


def _tool_map(available_tools: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(tool.get("provider") or ""), str(tool.get("action_name") or "")): tool
        for tool in available_tools
        if tool.get("slug")
    }


def _planned_actions(
    steps: list[PlannedStep],
    available_tools: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    by_slug = {
        str(tool["slug"]): (
            str(tool.get("provider") or ""),
            str(tool.get("action_name") or ""),
        )
        for tool in available_tools
        if tool.get("slug")
    }
    return {
        by_slug[step.tool_slug]
        for step in steps
        if step.tool_slug is not None and step.tool_slug in by_slug
    }


def _first_number(order: str, nouns: str) -> int | None:
    patterns = (
        rf"\b(?:{nouns})\b\s*#?\s*(\d+)\b",
        rf"#(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, order, re.I)
        if match is not None:
            return int(match.group(1))
    return None


def _email_address(order: str) -> str | None:
    match = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        order,
        re.I,
    )
    return match.group(0) if match is not None else None


def _quoted_text(order: str) -> str | None:
    match = re.search(r'["“](.+?)["”]', order)
    if match is None:
        match = re.search(r"'(.+?)'", order)
    if match is None:
        return None
    text = match.group(1).strip()
    return text or None


def _branch_pair(order: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"\bfrom\s+([A-Za-z0-9._/-]+)\s+(?:into|to)\s+([A-Za-z0-9._/-]+)\b",
        order,
        re.I,
    )
    if match is not None:
        return match.group(1), match.group(2)
    head_match = re.search(
        r"\b(?:branch|head)\s+([A-Za-z0-9._/-]+)\b",
        order,
        re.I,
    )
    return (head_match.group(1), None) if head_match is not None else (None, None)


def _workflow_id(order: str) -> str | None:
    file_match = re.search(r"\b([A-Za-z0-9._/-]+\.ya?ml)\b", order, re.I)
    if file_match is not None:
        return file_match.group(1)
    named = re.search(
        r"\bworkflow\s+(?:named\s+)?([A-Za-z0-9._/-]+)\b",
        order,
        re.I,
    )
    return named.group(1) if named is not None else None


def _input_for_action(
    order: str,
    *,
    provider: str,
    action_name: str,
) -> dict[str, Any]:
    if provider == "gmail" and action_name == "send-message":
        recipient = _email_address(order)
        payload: dict[str, Any] = {
            "subject": "Seldrune owner order",
            "body": order.strip(),
        }
        if recipient:
            payload["to"] = recipient
        return payload

    if provider == "render" and action_name == "deploy-service":
        return {}

    if provider != "github":
        return {}

    if action_name == "merge-pull-request":
        number = _first_number(order, r"pr|pull request")
        return {"pull_number": number} if number is not None else {}

    if action_name == "create-issue":
        quoted = _quoted_text(order)
        title = quoted or order.strip()
        return {"title": title[:240]}

    if action_name == "comment":
        number = _first_number(order, r"issue|pr|pull request")
        body = _quoted_text(order) or order.strip()
        payload = {"body": body}
        if number is not None:
            payload["number"] = number
        return payload

    if action_name == "create-pull-request":
        head, base = _branch_pair(order)
        payload = {
            "title": (_quoted_text(order) or order.strip())[:240],
        }
        if head:
            payload["head"] = head
        if base:
            payload["base"] = base
        return payload

    if action_name == "dispatch-workflow":
        workflow_id = _workflow_id(order)
        return {"workflow_id": workflow_id} if workflow_id else {}

    return {}


def _missing_required_fields(
    tool: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    schema = tool.get("input_schema") or {}
    required = schema.get("required") or []
    if not isinstance(required, list):
        return []
    missing: list[str] = []
    for field in required:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(str(field))
    return sorted(missing)


_DIRECT_ACTION_ORDER = re.compile(
    r"^\\s*(?:"
    r"merge\\b|deploy\\b|redeploy\\b|send\\b|email\\b|mail\\b|notify\\b|"
    r"create\\s+(?:an?\\s+)?(?:issue|bug|pull request|pr)\\b|"
    r"open\\s+(?:an?\\s+)?(?:issue|bug|pull request|pr)\\b|"
    r"comment\\b|reply\\b|trigger\\b|dispatch\\b|run\\s+(?:the\\s+)?workflow\\b"
    r")",
    re.I,
)


def compile_required_external_action_steps(
    order: str,
    *,
    available_tools: list[dict[str, Any]],
    planned_steps: list[PlannedStep],
) -> tuple[list[PlannedStep], dict[str, Any]]:
    required_actions = required_external_tool_actions(order)
    planned_actions = _planned_actions(planned_steps, available_tools)
    tools = _tool_map(available_tools)
    added: list[PlannedStep] = []
    unresolved: list[dict[str, Any]] = []

    for provider, action_name in required_actions:
        key = (provider, action_name)
        if key in planned_actions:
            continue
        tool = tools.get(key)
        if tool is None:
            unresolved.append(
                {
                    "provider": provider,
                    "action_name": action_name,
                    "reason": "tool_unavailable",
                    "missing_fields": [],
                }
            )
            continue

        payload = _input_for_action(
            order,
            provider=provider,
            action_name=action_name,
        )
        missing_fields = _missing_required_fields(tool, payload)
        if missing_fields:
            unresolved.append(
                {
                    "provider": provider,
                    "action_name": action_name,
                    "reason": "required_input_unresolved",
                    "missing_fields": missing_fields,
                }
            )
            continue

        added.append(
            PlannedStep(
                f"Execute {tool.get('name') or tool['slug']}",
                f"Perform the owner's requested external action: {order}",
                ["engineering"],
                100,
                False,
                str(tool["slug"]),
                payload,
            )
        )

    direct_action = bool(required_actions and _DIRECT_ACTION_ORDER.search(order))
    unresolved_actions = bool(unresolved)
    if direct_action and added and not unresolved_actions:
        compiled_steps = added
        mode = "direct-tool-plan"
    else:
        compiled_steps = [*planned_steps, *added]
        mode = "append-missing-tools" if added else "planner-only"

    return compiled_steps, {
        "mode": mode,
        "required_actions": [
            f"{provider}:{action_name}"
            for provider, action_name in required_actions
        ],
        "added_tool_slugs": [step.tool_slug for step in added if step.tool_slug],
        "unresolved": unresolved,
    }
