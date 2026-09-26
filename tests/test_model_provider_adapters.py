import pytest

from backend.app.core.config import Settings
from backend.app.core.modeling import (
    ModelGatewayError,
    ModelImageInput,
    ModelProvider,
    ModelRequest,
)
from backend.app.services.model_gateway import ModelGateway, model_provider_capabilities


class FakeResponse:
    def __init__(self, body: dict):
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.call = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
        self.call = {"url": url, "headers": headers, "json": json}
        return self.response


def _request(provider: ModelProvider, model: str) -> ModelRequest:
    return ModelRequest(
        provider=provider,
        model=model,
        input_text="hello",
        instructions="Be helpful.",
        max_output_tokens=100,
        max_estimated_cost_usd=0.04,
    )


def test_gemini_interactions_adapter_parses_output_and_usage(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        gemini_api_key="gemini-test-secret",
    )
    fake = FakeClient(
        FakeResponse(
            {
                "id": "interaction-1",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": "Hello from Gemini"}],
                    }
                ],
                "usage": {
                    "total_input_tokens": 20,
                    "total_output_tokens": 5,
                    "total_tokens": 25,
                },
            }
        )
    )
    monkeypatch.setattr(
        "backend.app.services.model_gateway.httpx.Client",
        lambda **kwargs: fake,
    )

    result, latency = ModelGateway(settings).generate(
        _request(ModelProvider.GEMINI, settings.gemini_model)
    )

    assert result.output_text == "Hello from Gemini"
    assert result.response_id == "interaction-1"
    assert result.usage.input_tokens == 20
    assert result.usage.output_tokens == 5
    assert result.usage.estimated_cost_usd is not None
    assert result.provider == ModelProvider.GEMINI
    assert latency >= 0
    assert fake.call["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert fake.call["headers"]["x-goog-api-key"] == "gemini-test-secret"
    assert fake.call["json"]["system_instruction"] == "Be helpful."
    assert fake.call["json"]["store"] is False
    assert fake.call["json"]["generation_config"]["max_output_tokens"] == 100


def test_anthropic_messages_adapter_parses_output_and_usage(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        anthropic_api_key="anthropic-test-secret",
    )
    fake = FakeClient(
        FakeResponse(
            {
                "id": "message-1",
                "content": [{"type": "text", "text": "Hello from Claude"}],
                "usage": {"input_tokens": 25, "output_tokens": 8},
            }
        )
    )
    monkeypatch.setattr(
        "backend.app.services.model_gateway.httpx.Client",
        lambda **kwargs: fake,
    )

    result, _latency = ModelGateway(settings).generate(
        _request(ModelProvider.ANTHROPIC, settings.anthropic_model)
    )

    assert result.output_text == "Hello from Claude"
    assert result.response_id == "message-1"
    assert result.usage.total_tokens == 33
    assert result.usage.estimated_cost_usd is not None
    assert result.provider == ModelProvider.ANTHROPIC
    assert fake.call["url"] == "https://api.anthropic.com/v1/messages"
    assert fake.call["headers"]["x-api-key"] == "anthropic-test-secret"
    assert fake.call["headers"]["anthropic-version"] == "2023-06-01"
    assert fake.call["json"]["system"] == "Be helpful."
    assert fake.call["json"]["max_tokens"] == 100


def test_external_text_providers_require_keys_and_reject_attachments(monkeypatch) -> None:
    missing_key = Settings(_env_file=None, environment="test")
    with pytest.raises(ModelGatewayError, match="SELDRUNE_GEMINI_API_KEY"):
        ModelGateway(missing_key).generate(
            _request(ModelProvider.GEMINI, missing_key.gemini_model)
        )

    configured = Settings(
        _env_file=None,
        environment="test",
        gemini_api_key="test-key",
    )
    request = ModelRequest(
        provider=ModelProvider.GEMINI,
        model=configured.gemini_model,
        input_text="hello",
        input_images=(
            ModelImageInput(
                media_type="image/png",
                data_base64="aGVsbG8=",
            ),
        ),
    )
    with pytest.raises(ModelGatewayError, match="images"):
        ModelGateway(configured).generate(request)

    capabilities = model_provider_capabilities(ModelProvider.ANTHROPIC)
    assert capabilities.text
    assert not capabilities.images
    assert not capabilities.files
