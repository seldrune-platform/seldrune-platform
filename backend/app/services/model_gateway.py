from time import perf_counter
from typing import Any

from openai import OpenAI

from backend.app.core.config import Settings
from backend.app.core.modeling import (
    ModelGatewayError,
    ModelProvider,
    ModelRequest,
    ModelResult,
    ModelUsage,
)


class ModelGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, request: ModelRequest) -> tuple[ModelResult, int]:
        started = perf_counter()
        if request.provider is ModelProvider.MOCK:
            result = self._generate_mock(request)
        elif request.provider is ModelProvider.OPENAI:
            result = self._generate_openai(request)
        else:
            raise ModelGatewayError(f"Unsupported model provider: {request.provider}")
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        return result, latency_ms

    def _generate_mock(self, request: ModelRequest) -> ModelResult:
        input_tokens = max(1, len(request.input_text.split()))
        output = f"Mock execution completed. {request.input_text[:500]}"
        output_tokens = max(1, len(output.split()))
        return ModelResult(
            provider=ModelProvider.MOCK,
            model=request.model,
            output_text=output,
            response_id="mock-response",
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )

    def _generate_openai(self, request: ModelRequest) -> ModelResult:
        if not request.model or request.model.startswith("mock-"):
            raise ModelGatewayError("An OpenAI model must be configured")

        response_args: dict[str, Any] = {
            "model": request.model,
            "input": request.input_text,
            "instructions": request.instructions,
            "max_output_tokens": request.max_output_tokens,
        }
        if request.response_schema is not None:
            response_args["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "seldrune_response",
                    "strict": True,
                    "schema": request.response_schema,
                }
            }
        try:
            client = OpenAI(timeout=self.settings.model_timeout_seconds)
            response = client.responses.create(**response_args)
        except Exception as exc:
            raise ModelGatewayError(
                f"OpenAI request failed: {type(exc).__name__}"
            ) from exc

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_tokens", input_tokens + output_tokens) or 0
        )
        return ModelResult(
            provider=ModelProvider.OPENAI,
            model=request.model,
            output_text=getattr(response, "output_text", "") or "",
            response_id=getattr(response, "id", None),
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
        )
