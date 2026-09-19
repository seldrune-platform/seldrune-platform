import pytest

from services.supreme.creativity import CandidateIdea, diverse_frontier, rank_candidates


def test_evidence_can_beat_unsupported_novelty():
    grounded = CandidateIdea("a", "grounded", 0.8, 0.9, 0.9)
    fantasy = CandidateIdea("b", "fantasy", 1.0, 0.1, 0.0)
    assert rank_candidates((fantasy, grounded))[0] == grounded


def test_frontier_removes_word_order_duplicates():
    a = CandidateIdea("a", "parallel expert routing", 0.8, 0.8, 0.8)
    b = CandidateIdea("b", "routing parallel expert", 0.7, 0.7, 0.7)
    assert diverse_frontier((a, b), 2) == (a,)


def test_frontier_requires_positive_limit():
    with pytest.raises(ValueError):
        diverse_frontier((), 0)
