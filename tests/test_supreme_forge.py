from services.supreme.forge import Benchmark, candidate_beats_baseline, next_experiment


def test_candidate_requires_measured_improvement_without_regression():
    baseline = Benchmark(0.80, 0.70, 100.0, 20.0)
    candidate = Benchmark(0.84, 0.72, 90.0, 18.0)
    assert candidate_beats_baseline(candidate, baseline)


def test_faster_but_less_accurate_candidate_is_rejected():
    baseline = Benchmark(0.80, 0.70, 100.0, 20.0)
    candidate = Benchmark(0.79, 0.72, 80.0, 15.0)
    assert not candidate_beats_baseline(candidate, baseline)


def test_identical_candidate_is_not_an_improvement():
    baseline = Benchmark(0.80, 0.70, 100.0, 20.0)
    assert not candidate_beats_baseline(baseline, baseline)


def test_experiment_starts_as_proposed():
    experiment = next_experiment("forge-001", "Improve expert routing")
    assert experiment.experiment_id == "forge-001"
    assert experiment.state.value == "proposed"
