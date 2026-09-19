import pytest

from services.supreme.skill_evolution import (
    Skill,
    SkillState,
    candidate_skill,
    learning_frontier,
    verify_skill,
)


def test_candidate_requires_measured_evidence():
    with pytest.raises(ValueError, match="evidence"):
        candidate_skill(Skill("vision", "visual reasoning"), 0.9, 0)


def test_verified_skill_must_clear_threshold():
    candidate = candidate_skill(Skill("code", "software engineering"), 0.91, 50)
    verified = verify_skill(candidate)
    assert verified.state is SkillState.VERIFIED


def test_weak_candidate_is_not_promoted():
    candidate = candidate_skill(Skill("math", "mathematical reasoning"), 0.6, 30)
    with pytest.raises(ValueError, match="threshold"):
        verify_skill(candidate)


def test_learning_frontier_is_bounded_and_parallel():
    skills = (
        Skill("research", "deep research"),
        Skill("vision", "vision"),
        Skill("voice", "speech"),
    )
    frontier = learning_frontier(skills, 2)
    assert len(frontier) == 2
    assert {item.skill_id for item in frontier} == {"research", "vision"}
