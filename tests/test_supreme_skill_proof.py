import pytest

from services.supreme.proof_mesh import ProofVerdict
from services.supreme.skill_evolution import Skill, candidate_skill
from services.supreme.skill_proof import evaluate_skill, promote_verified_skill
from services.supreme.verifiers import threshold_check


def test_measured_proof_promotes_candidate_skill():
    skill = candidate_skill(Skill("reasoning", "reasoning"), 0.92, 100)
    checks = (
        threshold_check("accuracy", 0.92, 0.85, "artifact://accuracy"),
        threshold_check(
            "latency-ms", 140, 200, "artifact://latency", lower_is_better=True
        ),
    )
    proof = evaluate_skill(skill, checks)
    promoted = promote_verified_skill(skill, proof)
    assert proof.verdict is ProofVerdict.VERIFIED
    assert promoted.state.value == "verified"


def test_failed_measurement_blocks_promotion():
    skill = candidate_skill(Skill("research", "research"), 0.9, 50)
    proof = evaluate_skill(
        skill,
        (threshold_check("accuracy", 0.7, 0.85, "artifact://accuracy"),),
    )
    assert proof.verdict is ProofVerdict.REJECTED
    with pytest.raises(ValueError, match="rejected"):
        promote_verified_skill(skill, proof)
