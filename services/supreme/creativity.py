"""Creativity engine for SUPREME: diverse hypotheses before convergence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateIdea:
    idea_id: str
    hypothesis: str
    novelty: float
    feasibility: float
    evidence: float


def rank_candidates(candidates: tuple[CandidateIdea, ...]) -> tuple[CandidateIdea, ...]:
    """Prefer novel ideas only when feasibility and evidence remain meaningful."""
    def score(item: CandidateIdea) -> float:
        return 0.40 * item.novelty + 0.30 * item.feasibility + 0.30 * item.evidence

    return tuple(sorted(candidates, key=score, reverse=True))


def diverse_frontier(
    candidates: tuple[CandidateIdea, ...], limit: int
) -> tuple[CandidateIdea, ...]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    seen: set[str] = set()
    selected: list[CandidateIdea] = []
    for item in rank_candidates(candidates):
        fingerprint = " ".join(sorted(set(item.hypothesis.lower().split())))
        if fingerprint not in seen:
            selected.append(item)
            seen.add(fingerprint)
        if len(selected) == limit:
            break
    return tuple(selected)
