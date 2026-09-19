import pytest

from services.aetherion.execution_planner import (
    WorkloadProfile,
    build_plan,
    live_media_profile,
)


def test_planner_prefers_reuse_for_temporally_similar_workload():
    profile = WorkloadProfile(0.95, 0.2, 0.9, 0.7, 0.8)
    plan = build_plan(profile)
    assert "temporal-delta-execution" in plan.strategies
    assert "predictive-tensor-reuse" in plan.strategies
    assert not plan.measured
    assert not plan.hardware_benchmark


def test_live_media_profile_exposes_parallel_and_fusion_opportunity():
    profile = live_media_profile(
        temporal_similarity=0.9,
        sparsity=0.4,
        locality=0.85,
    )
    plan = build_plan(profile)
    assert "workload-specific-kernel-fusion" in plan.strategies
    assert "speculative-parallel-branches" in plan.strategies


def test_invalid_workload_profile_is_rejected():
    profile = WorkloadProfile(1.1, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        build_plan(profile)
