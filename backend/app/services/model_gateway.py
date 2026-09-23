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
from backend.app.services.ai_cost_governor import estimate_model_cost


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

    @staticmethod
    def _rough_input_token_estimate(
        request: ModelRequest,
        decoded_file_bytes: int,
    ) -> int:
        text_chars = len(request.input_text) + len(request.instructions or "")
        text_tokens = max(1, (text_chars + 3) // 4)
        image_tokens = 1200 * len(request.input_images)
        # Exact multimodal counting is preferred. This intentionally conservative
        # fallback protects the budget if token-count preflight is unavailable.
        file_tokens = max(0, decoded_file_bytes // 3)
        return text_tokens + image_tokens + file_tokens

    def _guard_request_cost(
        self,
        request: ModelRequest,
        *,
        input_tokens: int,
    ) -> None:
        budget = request.max_estimated_cost_usd
        if budget is None:
            return
        max_output_tokens = max(0, int(request.max_output_tokens or 0))
        worst_case = estimate_model_cost(
            request.model,
            input_tokens=input_tokens,
            output_tokens=max_output_tokens,
        )
        if worst_case is None:
            return
        if worst_case > budget:
            raise ModelGatewayError(
                "AI cost governor blocked request before generation: "
                f"estimated maximum USD {worst_case:.4f} exceeds "
                f"USD {budget:.4f} request budget"
            )

    def _generate_openai(self, request: ModelRequest) -> ModelResult:
        if not request.model or request.model.startswith("mock-"):
            raise ModelGatewayError("An OpenAI model must be configured")

        client = OpenAI(timeout=self.settings.model_timeout_seconds)
        uploaded_file_ids: list[str] = []
        decoded_file_bytes = 0
        try:
            model_input: Any = request.input_text
            if request.input_images or request.input_files:
                # Reusable heavy inputs come before the changing instruction text
                # so repeated work can reuse a larger cached prompt prefix.
                content: list[dict[str, Any]] = []
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
                    decoded_file_bytes += len(file_bytes)
                    uploaded = client.files.create(
                        file=(
                            file_input.filename,
                            file_bytes,
                            file_input.media_type or "application/octet-stream",
                        ),
                        purpose="user_data",
                    )
                    uploaded_file_ids.append(uploaded.id)
                    item: dict[str, Any] = {
                        "type": "input_file",
                        "file_id": uploaded.id,
                    }
                    if (file_input.media_type or "").lower() == "application/pdf":
                        item["detail"] = request.pdf_detail
                    content.append(item)

                for image in request.input_images:
                    content.append(
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{image.media_type};base64,{image.data_base64}"
                            ),
                            "detail": request.image_detail,
                        }
                    )

                content.append({"type": "input_text", "text": request.input_text})
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
            if request.reasoning_effort and request.model.startswith("gpt-5.6"):
                response_args["reasoning"] = {
                    "effort": request.reasoning_effort,
                }
            if (
                self.settings.ai_prompt_cache_enabled
                and request.prompt_cache_key
            ):
                response_args["prompt_cache_key"] = request.prompt_cache_key[:512]
                if request.model.startswith("gpt-5.6"):
                    response_args["prompt_cache_options"] = {"ttl": "30m"}

            if request.max_estimated_cost_usd is not None:
                preflight_tokens: int | None = None
                if (
                    request.exact_token_preflight
                    and self.settings.ai_exact_token_preflight
                ):
                    try:
                        count = client.responses.input_tokens.count(
                            model=request.model,
                            input=model_input,
                            instructions=request.instructions,
                        )
                        preflight_tokens = int(
                            getattr(count, "input_tokens", 0) or 0
                        )
                    except Exception:
                        preflight_tokens = None

                if not preflight_tokens:
                    preflight_tokens = self._rough_input_token_estimate(
                        request,
                        decoded_file_bytes,
                    )
                self._guard_request_cost(
                    request,
                    input_tokens=preflight_tokens,
                )

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
        input_details = getattr(usage, "input_tokens_details", None)
        cached_input_tokens = int(
            getattr(input_details, "cached_tokens", 0) or 0
        )
        cache_write_tokens = int(
            getattr(input_details, "cache_write_tokens", 0) or 0
        )
        estimated_cost = estimate_model_cost(
            request.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_tokens=cache_write_tokens,
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
                cached_input_tokens=cached_input_tokens,
                cache_write_tokens=cache_write_tokens,
                estimated_cost_usd=estimated_cost,
            ),
        )
