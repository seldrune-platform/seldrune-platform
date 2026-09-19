from services.supreme.recovery import plan_recovery
from services.supreme.skill_evolution import Skill
from services.supreme.verifiers import threshold_check


def test_failed_measurement_queues_forge_recovery_job():
    skill = Skill("face-quality", "LiveShift face quality")
    checks = (
        threshold_check("quality", 0.60, 0.85, "artifact://quality"),
        threshold_check(
            "latency-ms",
            140.0,
            200.0,
            "artifact://latency",
            lower_is_better=True,
        ),
    )

    plans = plan_recovery(skill, checks, generation=2)

    assert len(plans) == 1
    plan = plans[0]
    assert plan.objective.skill_id == "face-quality"
    assert plan.job.experiment_id == "skill-face-quality-g2"
    assert plan.job.accelerator == "rtx-pro-6000-blackwell"


def test_passing_measurements_create_no_recovery_work():
    skill = Skill("stream-latency", "LiveShift stream latency")
    checks = (
        threshold_check(
            "latency-ms",
            120.0,
            200.0,
            "artifact://latency",
            lower_is_better=True,
        ),
    )

    assert plan_recovery(skill, checks, generation=1) == ()
