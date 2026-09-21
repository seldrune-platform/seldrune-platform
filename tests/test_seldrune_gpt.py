from types import SimpleNamespace
from unittest.mock import patch

from backend.app.core.config import settings
from backend.app.core.modeling import ModelResult, ModelUsage


def test_seldrune_gpt_requires_auth(client):
    response = client.post("/api/v1/organizations/00000000-0000-0000-0000-000000000001/gpt", json={"message": "hello"})
    assert response.status_code in {401, 403}


def test_gpt_response_schema_exposes_runtime_metadata():
    from backend.app.api.routes.seldrune_gpt import SeldruneGPTResponse

    response = SeldruneGPTResponse(
        model="test-model",
        response="hello",
        response_id="resp_1",
        input_tokens=3,
        output_tokens=4,
        latency_ms=12,
        provider="openai",
    )
    assert response.model == "test-model"
    assert response.latency_ms == 12
    assert response.provider == "openai"
