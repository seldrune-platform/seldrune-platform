import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.modeling import ModelProvider, ModelRequest
from backend.app.services.model_gateway import ModelGateway
from backend.app.services.model_provider_registry import model_provider_statuses
from backend.app.services.provider_preflight import preflight_provider_credential
from tests.test_autonomous_execution import register_owner


pytest_plugins = ["tests.test_autonomous_execution"]


class _ProviderListResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.content = b'{"data":[],"models":[]}'

    def json(self) -> dict:
        return {"data": [], "models": []}


class _GenerationResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "id": "interaction-test",
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": "Vault key works"}],
                }
            ],
            "usage": {
                "total_input_tokens": 5,
                "total_output_tokens": 4,
                "total_tokens": 9,
            },
        }


class _FakeGenerationClient:
    def __init__(self) -> None:
        self.call = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url: str, *, headers: dict, json: dict):
        self.call = {"url": url, "headers": headers, "json": json}
        return _GenerationResponse()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("provider", "expected_url", "expected_header"),
    [
        ("openai", "https://api.openai.com/v1/models", "Authorization"),
        (
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/models",
            "x-goog-api-key",
        ),
        ("anthropic", "https://api.anthropic.com/v1/models?limit=1", "x-api-key"),
    ],
)
def test_model_provider_preflight_checks_keys_without_returning_them(
    monkeypatch,
    provider: str,
    expected_url: str,
    expected_header: str,
) -> None:
    secret = provider + "-private-test-key"
    calls = []

    def fake_get(url: str, *, headers: dict, timeout: float):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return _ProviderListResponse()

    monkeypatch.setattr(
        "backend.app.services.provider_preflight.httpx.get",
        fake_get,
    )

    result = preflight_provider_credential(provider, secret)

    assert result["verified"] is True
    assert result["status"] == "verified"
    assert calls[0]["url"] == expected_url
    assert calls[0]["headers"][expected_header]
    assert secret not in str(result)
    if provider == "anthropic":
        assert calls[0]["headers"]["anthropic-version"] == "2023-06-01"
    if provider == "openai":
        assert calls[0]["headers"]["Authorization"] == f"Bearer {secret}"
    if provider == "gemini":
        assert calls[0]["headers"]["x-goog-api-key"] == secret
    if provider == "anthropic":
        assert calls[0]["headers"]["x-api-key"] == secret


def test_model_provider_status_reports_vault_source_without_secret(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(_env_file=None, environment="test", model_provider="openai")

    statuses = model_provider_statuses(settings, vault_configured={"openai"})
    openai = next(item for item in statuses if item["provider"] == "openai")

    assert openai["configured"] is True
    assert openai["source"] == "vault"
    assert "private-test-key" not in str(statuses)


def test_model_gateway_uses_organization_vault_key_override(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        gemini_api_key="server-key",
    )
    client = _FakeGenerationClient()
    monkeypatch.setattr(
        "backend.app.services.model_gateway.httpx.Client",
        lambda **kwargs: client,
    )
    request = ModelRequest(
        provider=ModelProvider.GEMINI,
        model=settings.gemini_model,
        input_text="Say hello.",
        instructions="Be concise.",
        max_output_tokens=30,
    )

    result, _latency = ModelGateway(
        settings,
        api_key_overrides={ModelProvider.GEMINI: "organization-vault-key"},
    ).generate(request)

    assert result.output_text == "Vault key works"
    assert client.call["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/interactions"
    )
    assert client.call["headers"]["x-goog-api-key"] == "organization-vault-key"


def test_owner_can_connect_list_and_disconnect_model_api_key_without_exposure(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    token, organization_id = register_owner(client)
    secret = "openai-test-key-not-for-return"
    headers = _headers(token)
    base_url = f"/api/v1/organizations/{organization_id}/model-provider-connections"

    def verified(provider: str, credential: str) -> dict:
        assert provider == "openai"
        assert credential == secret
        return {
            "provider": provider,
            "status": "verified",
            "verified": True,
            "detail": "OpenAI API key can list available models.",
            "identity": {"models_available": 2},
            "http_status": 200,
        }

    monkeypatch.setattr(
        "backend.app.api.routes.model_provider_connections.preflight_provider_credential",
        verified,
    )

    connected = client.post(
        f"{base_url}/openai",
        headers=headers,
        json={"secret_value": secret},
    )
    assert connected.status_code == 200
    assert secret not in connected.text
    assert connected.json()["source"] == "vault"

    status_response = client.get(base_url, headers=headers)
    assert status_response.status_code == 200
    openai = next(
        item for item in status_response.json()["providers"]
        if item["provider"] == "openai"
    )
    assert openai["configured"] is True
    assert openai["source"] == "vault"
    assert secret not in status_response.text

    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    )
    assert references.status_code == 200
    reference = next(
        item for item in references.json()
        if item["slug"] == "model-openai-api-key"
    )
    assert reference["locator"] == "vault://stored"
    assert secret not in references.text

    disconnected = client.delete(f"{base_url}/openai", headers=headers)
    assert disconnected.status_code == 200
    assert disconnected.json()["configured"] is False
    assert secret not in disconnected.text


def test_rejected_model_api_key_is_not_saved(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    token, organization_id = register_owner(client)
    secret = "invalid-openai-private-key"
    headers = _headers(token)
    base_url = f"/api/v1/organizations/{organization_id}/model-provider-connections"

    monkeypatch.setattr(
        "backend.app.api.routes.model_provider_connections.preflight_provider_credential",
        lambda provider, credential: {
            "provider": provider,
            "status": "credential_invalid",
            "verified": False,
            "detail": "OpenAI rejected the API key.",
            "identity": {},
            "http_status": 401,
        },
    )
    response = client.post(
        f"{base_url}/openai",
        headers=headers,
        json={"secret_value": secret},
    )

    assert response.status_code == 422
    assert secret not in response.text
    statuses = client.get(base_url, headers=headers).json()["providers"]
    openai = next(item for item in statuses if item["provider"] == "openai")
    assert openai["configured"] is False
    references = client.get(
        f"/api/v1/organizations/{organization_id}/secret-references",
        headers=headers,
    ).json()
    assert all(item["slug"] != "model-openai-api-key" for item in references)
