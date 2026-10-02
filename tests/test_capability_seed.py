from types import SimpleNamespace
from uuid import uuid4

from backend.app.core.modeling import ModelProvider
from backend.app.services.agent_runtime import _build_input, _build_instructions
from backend.app.services.ai_cost_governor import estimate_model_cost
from backend.app.services.shared_agent_context import (
    append_owner_continuity,
    load_owner_continuity,
    resolve_requested_model,
)


def _agent(instructions: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        name="Research Agent",
        capabilities=["research", "analysis"],
        runtime_config={"instructions": instructions},
    )


def test_capability_seed_is_appended_to_custom_agent_instructions() -> None:
    custom = "Act as a careful research specialist."
    instructions = _build_instructions(_agent(custom))

    assert instructions.startswith(custom)
    assert "Seldrune collaborative execution seed" in instructions
    assert (\n        "Keep established facts distinct from assumptions and testable hypotheses"\n        in instructions\n    )
    assert "model statement alone is not completion proof" in instructions
    assert "compact skill capsules" in instructions
    assert "required owner approval" in instructions


def test_capability_seed_is_appended_to_default_agent_instructions() -> None:
    instructions = _build_instructions(_agent())

    assert "You are Research Agent" in instructions
    assert "research, analysis" in instructions
    assert "Seldrune collaborative execution seed" in instructions
    assert "acceptance evidence" in instructions


def test_owner_continuity_is_labeled_and_appended_to_agent_input() -> None:
    task = SimpleNamespace(
        title="Research",
        objective="Find a verified answer",
        input_data={},
    )
    built = _build_input(task, "Retrieved source note", "Keep explanations concise.")

    assert "Retrieved source note" in built
    assert "Owner-approved continuity preferences" in built
    assert "Keep explanations concise." in built


def test_owner_continuity_lookup_is_scoped_to_actor_and_organization() -> None:
    organization_id = uuid4()
    actor_user_id = uuid4()

    class Scalars:
        def first(self):
            return SimpleNamespace(content="  remember our working style  ")

    class Session:
        statement = None

        def scalars(self, statement):
            self.statement = statement
            return Scalars()

    session = Session()
    assert load_owner_continuity(session, organization_id, actor_user_id) == (
        "remember our working style"
    )

    params = session.statement.compile().params
    assert organization_id in params.values()
    assert actor_user_id in params.values()
    assert f"sense:owner-continuity:{actor_user_id}" in params.values()


def test_openai_route_defaults_to_gpt_6_luna_and_keeps_explicit_override() -> None:
    assert (
        resolve_requested_model(ModelProvider.OPENAI, None, "gpt-6-luna")
        == "gpt-6-luna"
    )
    assert (
        resolve_requested_model(
            ModelProvider.OPENAI,
            "gpt-6-astra",
            "gpt-6-luna",
        )
        == "gpt-6-astra"
    )
    assert (
        resolve_requested_model(
            ModelProvider.GEMINI,
            None,
            "gpt-6-luna",
        )
        is None
    )


def test_gpt_6_luna_cost_estimate_matches_per_million_rates() -> None:
    assert estimate_model_cost(
        "gpt-6-luna",
        input_tokens=100_000,
        output_tokens=100_000,
    ) == 0.06


def test_empty_continuity_does_not_change_input() -> None:
    original = "Task: check the service"
    assert append_owner_continuity(original, "  ") == original
