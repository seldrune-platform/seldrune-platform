from types import SimpleNamespace

from backend.app.services.agent_runtime import _build_instructions


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
    assert "Seldrune execution seed:" in instructions
    assert "separate source claims, assumptions, and unknowns" in instructions
    assert "model claim alone is not completion evidence" in instructions
    assert "compact skill capsule" in instructions


def test_capability_seed_is_appended_to_default_agent_instructions() -> None:
    instructions = _build_instructions(_agent())

    assert "You are Research Agent" in instructions
    assert "research, analysis" in instructions
    assert "Seldrune execution seed:" in instructions
    assert "acceptance evidence" in instructions
