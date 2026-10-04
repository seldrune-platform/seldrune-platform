from backend.app.core.orchestration import PlannedStep
from backend.app.services.owner_action_compiler import (
    compile_required_external_action_steps,
    required_external_tool_actions,
)


def _tool(
    slug: str,
    provider: str,
    action_name: str,
    required: list[str],
    *,
    defaults: list[str] | None = None,
) -> dict:
    return {
        "slug": slug,
        "name": slug,
        "provider": provider,
        "action_name": action_name,
        "risk_level": "medium",
        "input_defaults": defaults or [],
        "input_schema": {
            "type": "object",
            "properties": {field: {"type": "string"} for field in required},
            "required": required,
        },
    }


def _generic_plan() -> list[PlannedStep]:
    return [
        PlannedStep(
            "Analyze order",
            "Analyze the owner order.",
            ["analysis"],
            10,
        )
    ]


def test_required_actions_preserve_owner_phrase_order() -> None:
    actions = required_external_tool_actions(
        "Deploy production and notify the owner by email"
    )
    assert actions == [
        ("render", "deploy-service"),
        ("gmail", "send-message"),
    ]


def test_direct_merge_replaces_generic_plan_with_single_tool_step() -> None:
    tools = [
        _tool(
            "github-merge-pull-request",
            "github",
            "merge-pull-request",
            ["pull_number"],
            defaults=["owner", "repo"],
        )
    ]
    steps, metadata = compile_required_external_action_steps(
        "Merge PR 233",
        available_tools=tools,
        planned_steps=_generic_plan(),
    )
    assert metadata["mode"] == "direct-tool-plan"
    assert metadata["added_tool_slugs"] == ["github-merge-pull-request"]
    assert metadata["unresolved"] == []
    assert len(steps) == 1
    assert steps[0].tool_slug == "github-merge-pull-request"
    assert steps[0].tool_input == {"pull_number": 233}


def test_direct_deploy_can_rely_on_runtime_default_service() -> None:
    tools = [
        _tool(
            "render-deploy-service",
            "render",
            "deploy-service",
            [],
            defaults=["service_id"],
        )
    ]
    steps, metadata = compile_required_external_action_steps(
        "Deploy production",
        available_tools=tools,
        planned_steps=_generic_plan(),
    )
    assert metadata["mode"] == "direct-tool-plan"
    assert len(steps) == 1
    assert steps[0].tool_slug == "render-deploy-service"
    assert steps[0].tool_input == {}


def test_direct_email_uses_owner_runtime_default_when_address_omitted() -> None:
    tools = [
        _tool(
            "gmail-send-message",
            "gmail",
            "send-message",
            ["subject", "body"],
            defaults=["to"],
        )
    ]
    steps, metadata = compile_required_external_action_steps(
        "Send an email to the owner with the current release status",
        available_tools=tools,
        planned_steps=_generic_plan(),
    )
    assert metadata["mode"] == "direct-tool-plan"
    assert len(steps) == 1
    assert steps[0].tool_input == {
        "subject": "Seldrune owner order",
        "body": "Send an email to the owner with the current release status",
    }


def test_ambiguous_create_pull_request_is_not_guessed() -> None:
    tools = [
        _tool(
            "github-create-pull-request",
            "github",
            "create-pull-request",
            ["title", "head"],
            defaults=["owner", "repo", "base"],
        )
    ]
    original = _generic_plan()
    steps, metadata = compile_required_external_action_steps(
        "Create a pull request",
        available_tools=tools,
        planned_steps=original,
    )
    assert steps == original
    assert metadata["mode"] == "planner-only"
    assert metadata["configuration_hints"] == []
    assert metadata["unresolved_user_fields"] == ["head"]
    assert metadata["unresolved"] == [
        {
            "provider": "github",
            "action_name": "create-pull-request",
            "reason": "required_input_unresolved",
            "missing_fields": ["head"],
        }
    ]


def test_existing_planned_tool_is_not_duplicated() -> None:
    tool = _tool(
        "github-merge-pull-request",
        "github",
        "merge-pull-request",
        ["pull_number"],
        defaults=["owner", "repo"],
    )
    planned = [
        PlannedStep(
            "Merge pull request",
            "Merge PR 233.",
            ["engineering"],
            100,
            False,
            "github-merge-pull-request",
            {"pull_number": 233},
        )
    ]
    steps, metadata = compile_required_external_action_steps(
        "Merge PR 233",
        available_tools=[tool],
        planned_steps=planned,
    )
    assert steps == planned
    assert metadata["mode"] == "planner-only"
    assert metadata["added_tool_slugs"] == []


def test_repository_check_compiles_to_repository_info_tool() -> None:
    tools = [
        _tool(
            "github-repository-info",
            "github",
            "repository-info",
            [],
            defaults=["owner", "repo"],
        )
    ]
    steps, metadata = compile_required_external_action_steps(
        "Check repository",
        available_tools=tools,
        planned_steps=_generic_plan(),
    )
    assert metadata["mode"] == "direct-tool-plan"
    assert len(steps) == 1
    assert steps[0].tool_slug == "github-repository-info"
    assert steps[0].tool_input == {}


def test_read_repository_file_uses_default_repo_and_ref() -> None:
    tools = [
        _tool(
            "github-read-file",
            "github",
            "read-file",
            ["path"],
            defaults=["owner", "repo", "ref"],
        )
    ]
    steps, metadata = compile_required_external_action_steps(
        "Read file backend/app/main.py",
        available_tools=tools,
        planned_steps=_generic_plan(),
    )
    assert metadata["mode"] == "direct-tool-plan"
    assert steps[0].tool_input == {"path": "backend/app/main.py"}


def test_deploy_status_does_not_trigger_a_new_deploy() -> None:
    tools = [
        _tool(
            "render-deploy-status",
            "render",
            "deploy-status",
            ["deploy_id"],
            defaults=["service_id"],
        ),
        _tool(
            "render-deploy-service",
            "render",
            "deploy-service",
            [],
            defaults=["service_id"],
        ),
    ]
    steps, metadata = compile_required_external_action_steps(
        "Check deploy status dep-abc123",
        available_tools=tools,
        planned_steps=_generic_plan(),
    )
    assert metadata["required_actions"] == ["render:deploy-status"]
    assert len(steps) == 1
    assert steps[0].tool_slug == "render-deploy-status"
    assert steps[0].tool_input == {"deploy_id": "dep-abc123"}


def test_unreal_worker_intents_map_to_registered_tools() -> None:
    assert required_external_tool_actions("Check Unreal Engine status") == [
        ("unreal", "engine-status")
    ]
    assert required_external_tool_actions("Check Unreal Engine") == [
        ("unreal", "engine-status")
    ]
    assert required_external_tool_actions("Is Unreal Engine connected?") == [
        ("unreal", "engine-status")
    ]
    assert required_external_tool_actions("Download Unreal Engine 5.4") == [
        ("unreal", "install-engine")
    ]


def test_direct_unreal_install_sends_only_the_requested_version() -> None:
    tool = _tool("unreal-engine-install", "unreal", "install-engine", [])
    steps, metadata = compile_required_external_action_steps(
        "Download Unreal Engine 5.4.4",
        available_tools=[tool],
        planned_steps=_generic_plan(),
    )
    assert metadata["mode"] == "direct-tool-plan"
    assert metadata["added_tool_slugs"] == ["unreal-engine-install"]
    assert len(steps) == 1
    assert steps[0].tool_input == {"version": "5.4.4"}
