import pytest

from services.aetherion.research_kernel import (
    UniversalFactors,
    candidate_strategies,
    score_strategy,
)


def test_research_score_is_explicitly_not_measured():
    factors = UniversalFactors(0.2, 0.3, 0.2, 0.8, 0.9, 0.7, 0.8, 0.2)
    result = score_strategy("temporal-delta-execution", factors)
    assert 0 <= result.experimental_score <= 1
    assert result.measured is False


def test_invalid_factor_is_rejected():
    factors = UniversalFactors(2.0, 0, 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        score_strategy("invalid", factors)


def test_research_program_has_multiple_candidate_paths():
    assert len(candidate_strategies()) >= 8
