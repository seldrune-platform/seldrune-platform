import pytest

from services.supreme.skill_evolution import Skill, SkillState
from services.supreme.skill_promotion import promote_measured_skill
from services.supreme.verifiers import threshold_check


def test_measured_skill_can_be_verified():
    checks = (
        threshold_check("accuracy", 0.92, 0.85, "artifact://accuracy"),
        threshold_check(
            "latency-ms",
            140.0,
            200.0,
            "artifact://latency",
            lower_is_better=True,
        ),
    )
    promotion = promote_measured_skill(
        Skill("reasoning", "counterfactual reasoning"),
        0.91,
        100,
        checks,
    )
    assert promotion.skill.state is SkillState.VERIFIED
    assert promotion.evidence == ("artifact://accuracy", "artifact://latency")


def test_failed_proof_blocks_skill_promotion():
    checks = (
        threshold_check("accuracy", 0.6, 0.85, "artifact://accuracy"),
    )
    with pytest.raises(ValueError, match="proof mesh"):
        promote_measured_skill(Skill("vision", "vision"), 0.9, 50, checks)
