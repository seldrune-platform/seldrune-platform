import pytest

from backend.app.services.organization_synthesis import (
    infer_domain_factories,
    synthesize_organization,
)


def test_synthesis_keeps_universal_core_and_adds_relevant_factories() -> None:
    blueprint = synthesize_organization(
        "Build a healthcare RCM automation platform, recruit a workforce, and deploy it to cloud"
    )

    slugs = {unit["slug"] for unit in blueprint["units"]}
    assert {"research", "strategy-analysis", "architecture", "engineering", "validation"} <= slugs
    assert {"healthcare", "automation", "software", "talent", "infrastructure"} <= set(
        blueprint["domain_factories"]
    )
    assert blueprint["principles"]["unknown_capabilities_fail_closed"] is True
    assert blueprint["principles"]["consequential_actions_require_approval"] is True


def test_game_is_a_factory_not_the_identity_of_the_os() -> None:
    blueprint = synthesize_organization("Create and validate an open world game in Unreal")

    assert "creative-game" in blueprint["domain_factories"]
    assert blueprint["version"] == "universal-org-v1"
    assert any(unit["slug"] == "research" for unit in blueprint["units"])


def test_factory_inference_is_deterministic_and_deduplicated() -> None:
    assert infer_domain_factories("automation agent workflow automation") == ["automation"]


def test_empty_objective_is_rejected() -> None:
    with pytest.raises(ValueError, match="Objective is required"):
        synthesize_organization("   ")
