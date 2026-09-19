"""Verified skill promotion bridge for Seldrune STI."""

from dataclasses import dataclass

from .skill_evolution import Skill, candidate_skill, verify_skill
from .verifiers import CheckResult, all_checks_pass


@dataclass(frozen=True)
class SkillPromotion:
    skill: Skill
    checks: tuple[CheckResult, ...]
    evidence: tuple[str, ...]


def promote_measured_skill(
    skill: Skill,
    success_rate: float,
    evidence_count: int,
    checks: tuple[CheckResult, ...],
    minimum_success_rate: float = 0.8,
) -> SkillPromotion:
    """Promote only when independent measured checks and skill threshold pass."""
    if not all_checks_pass(checks):
        raise ValueError("proof mesh checks did not pass")
    candidate = candidate_skill(skill, success_rate, evidence_count)
    verified = verify_skill(candidate, minimum_success_rate)
    evidence = tuple(check.evidence for check in checks)
    return SkillPromotion(verified, checks, evidence)
