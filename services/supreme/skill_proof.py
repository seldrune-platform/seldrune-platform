"""Measured Proof Mesh gate for STI skill promotion."""

from dataclasses import dataclass

from .proof_mesh import ProofVerdict
from .skill_evolution import Skill, SkillState, verify_skill
from .verifiers import CheckResult, all_checks_pass


@dataclass(frozen=True)
class SkillProof:
    skill_id: str
    verdict: ProofVerdict
    checks: tuple[CheckResult, ...]


def evaluate_skill(skill: Skill, checks: tuple[CheckResult, ...]) -> SkillProof:
    if skill.state is not SkillState.CANDIDATE:
        raise ValueError("Proof Mesh evaluates candidate skills only")
    verdict = (
        ProofVerdict.VERIFIED if all_checks_pass(checks) else ProofVerdict.REJECTED
    )
    return SkillProof(skill.skill_id, verdict, checks)


def promote_verified_skill(
    skill: Skill,
    proof: SkillProof,
    minimum_success_rate: float = 0.8,
) -> Skill:
    if proof.skill_id != skill.skill_id:
        raise ValueError("proof belongs to a different skill")
    if proof.verdict is not ProofVerdict.VERIFIED:
        raise ValueError("rejected proof cannot promote a skill")
    return verify_skill(skill, minimum_success_rate)
