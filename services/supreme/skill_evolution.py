"""ASEE: Autonomous Skill Evolution Engine for Seldrune STI.

Skills advance only through measured evidence. Candidate generation can run
in parallel; activation remains a separate verified release decision.
"""

from dataclasses import dataclass
from enum import StrEnum


class SkillState(StrEnum):
    DISCOVERED = "discovered"
    TRAINING = "training"
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    RETIRED = "retired"


@dataclass(frozen=True)
class Skill:
    skill_id: str
    description: str
    state: SkillState = SkillState.DISCOVERED
    success_rate: float = 0.0
    evidence_count: int = 0


def candidate_skill(
    skill: Skill, success_rate: float, evidence_count: int
) -> Skill:
    if not 0.0 <= success_rate <= 1.0:
        raise ValueError("success_rate must be between 0 and 1")
    if evidence_count < 1:
        raise ValueError("candidate skills require evidence")
    return Skill(
        skill.skill_id,
        skill.description,
        SkillState.CANDIDATE,
        success_rate,
        evidence_count,
    )


def verify_skill(skill: Skill, minimum_success_rate: float = 0.8) -> Skill:
    if skill.state is not SkillState.CANDIDATE:
        raise ValueError("only candidate skills can be verified")
    if skill.success_rate < minimum_success_rate:
        raise ValueError("skill has not met the verification threshold")
    return Skill(
        skill.skill_id,
        skill.description,
        SkillState.VERIFIED,
        skill.success_rate,
        skill.evidence_count,
    )


def learning_frontier(
    skills: tuple[Skill, ...], max_parallel: int
) -> tuple[Skill, ...]:
    if max_parallel < 1:
        raise ValueError("max_parallel must be at least 1")
    eligible = (
        skill
        for skill in skills
        if skill.state in {SkillState.DISCOVERED, SkillState.TRAINING}
    )
    return tuple(sorted(eligible, key=lambda item: item.skill_id)[:max_parallel])
