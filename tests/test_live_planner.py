from backend.app.core.modeling import ModelProvider, ModelResult, ModelUsage
from backend.app.services import live_planner


class SuccessfulPlannerGateway:
    def generate(self, request):
        assert request.metadata["purpose"] == "owner_command_planning"
        assert request.metadata["adaptive_planning"] is False
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
                    '"capability":"research","priority":30,"tool_slug":null,'
                    '"tool_input_json":null},'
                    '{"title":"Validate value","objective":"Analyze cost and expected value",'
                    '"capability":"analysis","priority":20,"tool_slug":null,'
                    '"tool_input_json":null},'
                    '{"title":"Prepare decision","objective":"Define a safe pilot and criteria",'
                    '"capability":"architecture","priority":10,"tool_slug":null,'
                    '"tool_input_json":null}'
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
    assert result.planner_version == "live-model-v3-adaptive"
    assert len(result.steps) == 3
    assert [step.required_capabilities for step in result.steps] == [
        ["research"],
        ["analysis"],
        ["architecture"],
    ]
    assert result.metadata["usage"]["total_tokens"] == 120
    assert result.metadata["adaptive_planning"]["applied"] is False


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
    assert result.planner_version == "deterministic-v3-adaptive"
    assert result.metadata["mode"] == "fallback"
    assert len(result.steps) == 3



class ToolPlannerGateway:
    def generate(self, request):
        schema = request.response_schema["properties"]["steps"]["items"]["properties"]
        assert "send-owner-email" in schema["tool_slug"]["enum"]
        assert "Available registered tools" in request.input_text
        assert '"input_defaults":["to"]' in request.input_text
        assert "never invent values for them" in request.input_text
        return (
            ModelResult(
                provider=ModelProvider.OPENAI,
                model=request.model,
                output_text=(
                    '{"steps":[{'
                    '"title":"Notify owner",'
                    '"objective":"Send the verified result to the owner",'
                    '"capability":"analysis",'
                    '"priority":50,'
                    '"tool_slug":"send-owner-email",'
                    '"tool_input_json":"{\\\"to\\\":\\\"owner@example.com\\\",'
                    '\\\"subject\\\":\\\"Done\\\",\\\"body\\\":\\\"Verified.\\\"}"'
                    '}]}'
                ),
                response_id="response-tool-1",
                usage=ModelUsage(input_tokens=20, output_tokens=30, total_tokens=50),
            ),
            20,
        )


def test_live_planner_selects_only_registered_tool(monkeypatch) -> None:
    monkeypatch.setattr(live_planner.settings, "model_provider", "openai")
    monkeypatch.setattr(live_planner.settings, "model_default", "gpt-test")
    result = live_planner.build_live_plan(
        "Send the verified result to the owner.",
        gateway=ToolPlannerGateway(),
        available_tools=[
            {
                "slug": "send-owner-email",
                "description": "Send an owner notification.",
                "provider": "gmail",
                "action_name": "send-message",
                "risk_level": "medium",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                },
                "input_defaults": ["to"],
            }
        ],
    )
    assert result.planner_version == "live-model-v3-adaptive"
    assert len(result.steps) == 1
    assert result.steps[0].tool_slug == "send-owner-email"
    assert result.steps[0].tool_input == {
        "to": "owner@example.com",
        "subject": "Done",
        "body": "Verified.",
    }
