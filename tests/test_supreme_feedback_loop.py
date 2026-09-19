from services.supreme.feedback_loop import failed_gaps, learning_objectives
from services.supreme.verifiers import threshold_check


def test_failed_checks_become_learning_gaps():
    checks = (
        threshold_check("accuracy", 0.70, 0.85, "artifact://accuracy"),
        threshold_check(
            "latency-ms",
            150.0,
            200.0,
            "artifact://latency",
            lower_is_better=True,
        ),
    )
    gaps = failed_gaps(checks)
    assert len(gaps) == 1
    assert gaps[0].check_name == "accuracy"


def test_failed_checks_create_asee_objectives():
    checks = (threshold_check("quality", 0.5, 0.8, "artifact://quality"),)
    objectives = learning_objectives("face-quality", checks)
    assert len(objectives) == 1
    assert objectives[0].skill_id == "face-quality"
    assert "quality" in objectives[0].gap
