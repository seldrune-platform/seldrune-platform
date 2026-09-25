from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.tools import ToolStatus
from backend.app.models.tool_definition import ToolDefinition
from backend.app.services.tool_input_defaults import production_runtime_targets


CONTRACT_VERSION = "stage-compiler-v1"


REPOSITORY_ARTIFACT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "artifacts": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string"},
                    "message": {"type": "string", "minLength": 1},
                },
                "required": ["path", "content", "message"],
                "additionalProperties": False,
            },
        },
        "acceptance_notes": {"type": "string"},
    },
    "required": ["artifacts", "acceptance_notes"],
    "additionalProperties": False,
}


_REPOSITORY_PROFILES = {
    "unarchi",
    "model_bus",
    "console",
    "cost_control",
    "tooling",
    "factory",
}


def _slug_fragment(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._/-]+", "-", value.strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-/")
    return normalized or "stage"


def _profile_for_stage(stage: dict[str, Any]) -> str:
    execution_mode = str(stage.get("execution_mode") or "automatic")
    workstream = str(stage.get("workstream") or "")
    capabilities = {
        str(item).strip().lower()
        for item in stage.get("capabilities") or []
        if str(item).strip()
    }

    if workstream == "live_media" or "gpu" in capabilities:
        return "external-resource"
    if "deployment" in capabilities or str(stage.get("id")) == "factory_deploy":
        return "deployment"
    if workstream in _REPOSITORY_PROFILES:
        return "repository-engineering"
    if execution_mode in {"owner-gated", "external-resource"}:
        return execution_mode
    return "model-evidence"


def _active_tools(
    session: Session,
    *,
    organization_id: UUID,
) -> dict[tuple[str, str], ToolDefinition]:
    tools = session.scalars(
        select(ToolDefinition).where(
            ToolDefinition.organization_id == organization_id,
            ToolDefinition.status == ToolStatus.ACTIVE.value,
        )
    )
    return {
        (tool.provider.lower(), tool.action_name): tool
        for tool in tools
    }


def _required_fields(tool: ToolDefinition | None) -> list[str]:
    if tool is None:
        return []
    schema = tool.input_schema or {}
    required = schema.get("required") if isinstance(schema, dict) else []
    if not isinstance(required, list):
        return []
    return sorted(str(item) for item in required)


def _compile_tool_step(
    tools: dict[tuple[str, str], ToolDefinition],
    *,
    step_id: str,
    provider: str,
    action_name: str,
    input_data: dict[str, Any] | None = None,
    bindings: dict[str, str] | None = None,
    acceptance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool = tools.get((provider, action_name))
    resolved_input = dict(input_data or {})
    field_bindings = dict(bindings or {})
    required = _required_fields(tool)
    missing = [
        field
        for field in required
        if field not in resolved_input and field not in field_bindings
    ]
    bound = [
        field
        for field in required
        if field in field_bindings and field not in resolved_input
    ]

    if tool is None:
        status = "tool-unavailable"
    elif missing:
        status = "input-unresolved"
    elif bound:
        status = "binding-required"
    else:
        status = "ready"

    return {
        "id": step_id,
        "kind": "tool",
        "provider": provider,
        "action_name": action_name,
        "tool_slug": tool.slug if tool is not None else None,
        "tool_id": str(tool.id) if tool is not None else None,
        "risk_level": tool.risk_level if tool is not None else None,
        "approval_mode": tool.approval_mode if tool is not None else None,
        "input": resolved_input,
        "bindings": field_bindings,
        "required_fields": required,
        "missing_fields": missing,
        "bound_fields": bound,
        "status": status,
        "acceptance": dict(acceptance or {}),
    }


def _repository_contract(
    tools: dict[tuple[str, str], ToolDefinition],
    *,
    stage: dict[str, Any],
) -> list[dict[str, Any]]:
    targets = production_runtime_targets()
    owner = targets.get("github_owner")
    repo = targets.get("github_repo")
    base_ref = targets.get("github_ref") or "main"
    branch = f"seldrune/{_slug_fragment(str(stage['id']))}"

    base = {
        key: value
        for key, value in {"owner": owner, "repo": repo}.items()
        if value
    }

    return [
        {
            "id": "produce-artifacts",
            "kind": "model",
            "status": "ready",
            "objective": (
                "Produce the minimal repository changes and test updates needed "
                f"to satisfy stage {stage['id']} without claiming completion."
            ),
            "output_contract": {
                "artifacts": [
                    {
                        "path": "repository-relative path",
                        "content": "complete UTF-8 file content",
                        "message": "commit message",
                    }
                ],
                "acceptance_notes": "machine-checkable acceptance notes",
            },
            "response_schema": REPOSITORY_ARTIFACT_RESPONSE_SCHEMA,
            "acceptance": {
                "model_output_is_completion_evidence": False,
            },
        },
        _compile_tool_step(
            tools,
            step_id="inspect-repository",
            provider="github",
            action_name="repository-info",
            input_data=base,
            acceptance={"receipt_required": True},
        ),
        _compile_tool_step(
            tools,
            step_id="create-stage-branch",
            provider="github",
            action_name="create-branch",
            input_data={
                **base,
                "branch": branch,
                "ref": base_ref,
            },
            acceptance={"receipt_required": True},
        ),
        _compile_tool_step(
            tools,
            step_id="write-artifacts",
            provider="github",
            action_name="upsert-file",
            input_data={
                **base,
                "branch": branch,
                "base_ref": base_ref,
                "message": f"stage: {stage['id']}",
            },
            bindings={
                "path": "model.artifacts[*].path",
                "content": "model.artifacts[*].content",
            },
            acceptance={
                "receipt_required": True,
                "repeat_for_each": "model.artifacts",
            },
        ),
        _compile_tool_step(
            tools,
            step_id="open-pull-request",
            provider="github",
            action_name="create-pull-request",
            input_data={
                **base,
                "title": str(stage.get("title") or stage["id"])[:240],
                "head": branch,
                "base": base_ref,
                "draft": False,
            },
            acceptance={"receipt_required": True},
        ),
        _compile_tool_step(
            tools,
            step_id="run-ci",
            provider="github",
            action_name="dispatch-workflow",
            input_data={
                **base,
                "workflow_id": "ci.yml",
                "ref": branch,
                "inputs": {},
            },
            acceptance={"receipt_required": True},
        ),
        _compile_tool_step(
            tools,
            step_id="verify-ci",
            provider="github",
            action_name="workflow-run-status",
            input_data=base,
            bindings={"run_id": "steps.run-ci.output.workflow_run_id"},
            acceptance={
                "receipt_required": True,
                "output_path": "conclusion",
                "equals": "success",
                "external_resource_path": "failure_classification",
                "external_resource_values": [
                    "hosted_runner_unavailable",
                    "github_actions_billing_block",
                    "github_actions_runner_unavailable",
                ],
                "pending_status_path": "status",
                "pending_status_values": [
                    "queued",
                    "in_progress",
                    "waiting",
                    "requested",
                    "pending",
                ],
            },
        ),
        _compile_tool_step(
            tools,
            step_id="merge-verified-pull-request",
            provider="github",
            action_name="merge-pull-request",
            input_data={
                **base,
                "merge_method": "squash",
            },
            bindings={
                "pull_number": "steps.open-pull-request.output.number",
                "sha": "steps.verify-ci.output.head_sha",
            },
            acceptance={
                "receipt_required": True,
                "output_path": "merged",
                "equals": True,
            },
        ),
    ]


def _deployment_contract(
    tools: dict[tuple[str, str], ToolDefinition],
    *,
    stage: dict[str, Any],
) -> list[dict[str, Any]]:
    targets = production_runtime_targets()
    service_id = targets.get("render_service_id")
    deploy_input = {"service_id": service_id} if service_id else {}
    status_input = {"service_id": service_id} if service_id else {}

    return [
        _compile_tool_step(
            tools,
            step_id="deploy-service",
            provider="render",
            action_name="deploy-service",
            input_data=deploy_input,
            bindings={"commit_id": "upstream.verified_commit_sha"},
            acceptance={"receipt_required": True},
        ),
        _compile_tool_step(
            tools,
            step_id="verify-deploy",
            provider="render",
            action_name="deploy-status",
            input_data=status_input,
            bindings={"deploy_id": "steps.deploy-service.output.deploy_id"},
            acceptance={
                "receipt_required": True,
                "output_path": "status",
                "in": ["live"],
                "pending_values": [
                    "created",
                    "build_in_progress",
                    "update_in_progress",
                    "pre_deploy_in_progress",
                ],
            },
        ),
    ]


def compile_stage_execution_contract(
    session: Session,
    *,
    organization_id: UUID,
    stage: dict[str, Any],
) -> dict[str, Any]:
    tools = _active_tools(session, organization_id=organization_id)
    profile = _profile_for_stage(stage)
    execution_mode = str(stage.get("execution_mode") or "automatic")

    if profile == "repository-engineering":
        steps = _repository_contract(tools, stage=stage)
    elif profile == "deployment":
        steps = _deployment_contract(tools, stage=stage)
    else:
        steps = [
            {
                "id": "model-work",
                "kind": "model",
                "status": "ready",
                "objective": str(stage.get("objective") or ""),
                "output_contract": {
                    "result": "structured stage result",
                    "evidence": "independent evidence references",
                },
                "acceptance": {
                    "model_output_is_completion_evidence": False,
                },
            }
        ]

    tool_steps = [step for step in steps if step.get("kind") == "tool"]
    blocking: list[str] = []
    runtime_bindings: list[str] = []
    for step in tool_steps:
        status = str(step.get("status") or "")
        if status == "tool-unavailable":
            blocking.append(
                f"tool_unavailable:{step.get('provider')}:{step.get('action_name')}"
            )
        elif status == "input-unresolved":
            blocking.append(
                f"input_unresolved:{step.get('id')}:"
                + ",".join(step.get("missing_fields") or [])
            )
        elif status == "binding-required":
            runtime_bindings.append(f"binding_required:{step.get('id')}")

    automatic_allowed = execution_mode == "automatic"
    if not automatic_allowed:
        blocking.append(f"execution_mode:{execution_mode}")
    executable_now = automatic_allowed and not blocking and bool(tool_steps)
    approval_gate_steps = [
        str(step["id"])
        for step in tool_steps
        if step.get("risk_level") == "high"
        or step.get("approval_mode") == "always"
    ]

    return {
        "version": CONTRACT_VERSION,
        "stage_id": str(stage["id"]),
        "title": str(stage.get("title") or stage["id"]),
        "profile": profile,
        "execution_mode": execution_mode,
        "required_capabilities": [
            str(item) for item in stage.get("capabilities") or []
        ],
        "steps": steps,
        "tool_step_count": len(tool_steps),
        "executable_now": executable_now,
        "blocking_reasons": sorted(set(blocking)),
        "runtime_binding_reasons": sorted(set(runtime_bindings)),
        "approval_gate_steps": approval_gate_steps,
        "evidence_contract": {
            "model_output_is_completion_evidence": False,
            "completion_requires_machine_evidence": True,
            "all_tool_acceptance_checks_required": bool(tool_steps),
        },
    }
