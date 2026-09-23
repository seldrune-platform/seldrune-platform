from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ModelProvider(StrEnum):
    MOCK = "mock"
    OPENAI = "openai"


class InvocationStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class ModelImageInput:
    media_type: str
    data_base64: str
    name: str | None = None


@dataclass(frozen=True)
class ModelFileInput:
    filename: str
    data_base64: str
    media_type: str | None = None


@dataclass(frozen=True)
class ModelRequest:
    provider: ModelProvider
    model: str
    input_text: str
    instructions: str | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    response_schema: dict[str, Any] | None = None
    input_images: tuple[ModelImageInput, ...] = ()
    input_files: tuple[ModelFileInput, ...] = ()
    image_detail: str = "low"
    pdf_detail: str = "low"
    reasoning_effort: str | None = None
    prompt_cache_key: str | None = None
    max_estimated_cost_usd: float | None = None
    exact_token_preflight: bool = False


@dataclass(frozen=True)
class ModelResult:
    provider: ModelProvider
    model: str
    output_text: str
    response_id: str | None = None
    usage: ModelUsage = field(default_factory=ModelUsage)


class ModelGatewayError(RuntimeError):
    pass
