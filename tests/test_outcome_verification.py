from types import SimpleNamespace

from backend.app.services import outcome_verification


def _assess(*, objective: str, outputs: list[str]):
    run = SimpleNamespace(id="run-1", status="succeeded", objective=objective)
    steps = [
        SimpleNamespace(task_id=f"task-{i}", sequence=i)
        for i in range(1, len(outputs) + 1)
    ]
    tasks = {
        step.task_id: SimpleNamespace(output_data={"text": text})
        for step, text in zip(steps, outputs, strict=True)
    }

    class Session:
        def scalars(self, _statement):
            return iter(steps)

        def get(self, _model, task_id):
            return tasks.get(task_id)

    return outcome_verification.assess_command_outcome(Session(), run=run)


def test_diagnostic_objective_can_report_verification_gap_without_failing():
    assessment = _assess(
        objective=(
            "Analyze system readiness, identify gaps, and propose development "
            "priorities. Do not make external changes."
        ),
        outputs=[
            "Assessment complete. Required verification is incomplete for deployment "
            "readiness. Gap: production smoke evidence is missing. Priority: collect "
            "that evidence next."
        ],
    )
    assert assessment.verdict == "achieved"
    assert assessment.promotable is True


def test_verification_objective_still_fails_when_verification_is_incomplete():
    assessment = _assess(
        objective=(
            "Verify that the live deployment is ready and all required checks have "
            "passed."
        ),
        outputs=["Required verification is incomplete."],
    )
    assert assessment.verdict == "not_achieved"
    assert assessment.promotable is False
