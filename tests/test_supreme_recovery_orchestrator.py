from services.supreme.recovery_orchestrator import plan_recovery
from services.supreme.skill_evolution import Skill
from services.supreme.verifiers import threshold_check


def test_recovery_queues_only_failed_measurements():
    skill = Skill("face-quality", "LiveShift face quality")
    checks = (
        threshold_check("identity", 0.60, 0.85, "artifact://identity"),
        threshold_check(
            "latency-ms",
            140.0,
            200.0,
            "artifact://latency",
            lower_is_better=True,
        ),
    )
    plan = plan_recovery(skill, checks, 1)
    assert plan.skill_id == "face-quality"
    assert len(plan.objectives) == 1
    assert len(plan.jobs) == 1
    assert plan.jobs[0].experiment_id == "skill-face-quality-g1"
    assert plan.jobs[0].accelerator == "rtx-pro-6000-blackwell"


def test_recovery_assigns_unique_generations_to_multiple_failures():
    skill = Skill("live-media", "Live media transformation")
    checks = (
        threshold_check("quality", 0.5, 0.8, "artifact://quality"),
        threshold_check("stability", 0.6, 0.9, "artifact://stability"),
    )
    plan = plan_recovery(skill, checks, 4)
    assert [job.experiment_id for job in plan.jobs] == [
        "skill-live-media-g4",
        "skill-live-media-g5",
    ]


def test_recovery_with_no_failed_checks_creates_no_jobs():
    skill = Skill("verified", "Verified capability")
    checks = (threshold_check("quality", 0.9, 0.8, "artifact://quality"),)
    plan = plan_recovery(skill, checks, 1)
    assert plan.objectives == ()
    assert plan.jobs == ()
