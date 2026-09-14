from backend.app.core.modeling import ModelProvider, ModelResult, ModelUsage
from backend.app.services import live_planner


class SuccessfulPlannerGateway:
    def generate(self, request):
        assert request.metadata["purpose"] == "owner_command_planning"
        schema = request.response_schema["properties"]["steps"]
        assert schema["minItems"] == 3
        assert schema["maxItems"] == 3
        return (
            ModelResult(
                provider=ModelProvider.OPENAI,
                model=request.model,
                output_text=(
                    '{"steps":['
                    '{"title":"Find opportunity","objective":"Research one suitable workflow",'
                    '"capability":"research","priority":30},'
                    '{"title":"Validate value","objective":"Analyze cost and expected value",'
                    '"capability":"analysis","priority":20},'
                    '{"title":"Prepare decision","objective":"Define a safe pilot and criteria",'
                    '"capability":"architecture","priority":10}'
                    "]}"
                ),
                response_id="response-123",
                usage=ModelUsage(input_tokens=40, output_tokens=80, total_tokens=120),
            ),
            25,
        )


def test_live_planner_accepts_structured_model_plan(monkeypatch) -> None:
    monkeypatch.setattr(live_planner.settings, "model_provider", "openai")
    monkeypatch.setattr(live_planner.settings, "model_default", "gpt-test")
    result = live_planner.build_live_plan(
        "Create exactly three planning steps without external actions.",
        gateway=SuccessfulPlannerGateway(),
    )
    assert result.planner_version == "live-model-v2"
    assert len(result.steps) == 3
    assert [step.required_capabilities for step in result.steps] == [
        ["research"],
        ["analysis"],
        ["architecture"],
    ]
    assert result.metadata["usage"]["total_tokens"] == 120


def test_live_planner_falls_back_with_exact_requested_count(monkeypatch) -> None:
    class InvalidGateway:
        def generate(self, request):
            return (
                ModelResult(
                    provider=ModelProvider.OPENAI,
                    model=request.model,
                    output_text="not-json",
                ),
                5,
            )

    monkeypatch.setattr(live_planner.settings, "model_provider", "openai")
    monkeypatch.setattr(live_planner.settings, "model_default", "gpt-test")
    result = live_planner.build_live_plan(
        "Create exactly three planning steps for an automation.",
        gateway=InvalidGateway(),
    )
    assert result.planner_version == "deterministic-v2"
    assert result.metadata["mode"] == "fallback"
    assert len(result.steps) == 3
