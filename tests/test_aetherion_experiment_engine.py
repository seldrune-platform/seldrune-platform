from services.aetherion.experiment_engine import (
    predictive_reuse,
    sparse_route,
    temporal_delta,
)


def test_temporal_delta_measures_and_counts_unchanged_bytes():
    result = temporal_delta(b"abcd", b"abXd")
    assert result.measured
    assert not result.hardware_benchmark
    assert result.operations_avoided == 3
    assert result.elapsed_ns >= 0


def test_predictive_reuse_avoids_recomputation_on_cache_hit():
    calls = []
    cache = {}

    def compute():
        calls.append(1)
        return b"tensor"

    first = predictive_reuse(cache, "identity", compute)
    second = predictive_reuse(cache, "identity", compute)
    assert first.operations_avoided == 0
    assert second.operations_avoided == 1
    assert len(calls) == 1
    assert first.output_digest == second.output_digest


def test_sparse_route_counts_pruned_values():
    result = sparse_route((0.01, 0.9, -0.02, 0.8), 0.1)
    assert result.operations_avoided == 2
    assert result.hardware_benchmark is False
