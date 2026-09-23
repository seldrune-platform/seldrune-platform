import base64
import binascii
from contextlib import suppress
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

        client = OpenAI(timeout=self.settings.model_timeout_seconds)
        uploaded_file_ids: list[str] = []
        try:
            model_input: Any = request.input_text
            if request.input_images or request.input_files:
                content: list[dict[str, Any]] = [
                    {"type": "input_text", "text": request.input_text}
                ]
                for image in request.input_images:
                    content.append(
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{image.media_type};base64,{image.data_base64}"
                            ),
                        }
                    )
                for file_input in request.input_files:
                    try:
                        file_bytes = base64.b64decode(
                            file_input.data_base64,
                            validate=True,
                        )
                    except (ValueError, binascii.Error) as exc:
                        raise ModelGatewayError(
                            f"Invalid base64 content for {file_input.filename}"
                        ) from exc
                    uploaded = client.files.create(
                        file=(
                            file_input.filename,
                            file_bytes,
                            file_input.media_type or "application/octet-stream",
                        ),
                        purpose="user_data",
                    )
                    uploaded_file_ids.append(uploaded.id)
                    content.append(
                        {
                            "type": "input_file",
                            "file_id": uploaded.id,
                        }
                    )
                model_input = [{"role": "user", "content": content}]

            response_args: dict[str, Any] = {
                "model": request.model,
                "input": model_input,
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
            response = client.responses.create(**response_args)
        except ModelGatewayError:
            raise
        except Exception as exc:
            detail = " ".join(str(exc).split())
            if len(detail) > 500:
                detail = detail[:497] + "..."
            suffix = f": {detail}" if detail else ""
            raise ModelGatewayError(
                f"OpenAI request failed ({type(exc).__name__}){suffix}"
            ) from exc
        finally:
            for file_id in uploaded_file_ids:
                with suppress(Exception):
                    client.files.delete(file_id)

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
