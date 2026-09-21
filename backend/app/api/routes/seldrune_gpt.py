from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from pydantic import BaseModel, Field

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.core.config import settings
from backend.app.core.modeling import ModelProvider, ModelRequest
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership
from backend.app.models.seldrune_gpt_message import SeldruneGPTMessage
from backend.app.services.model_gateway import ModelGateway, ModelGatewayError

router = APIRouter(prefix="/organizations", tags=["seldrune-gpt"])
run_dependency = require_org_permission(Permission.AGENTS_RUN)
AgentsRunDep = Annotated[Membership, Depends(run_dependency)]


class SeldruneGPTRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)


class SeldruneGPTHistoryMessage(BaseModel):
    role: str
    content: str
    model: str | None = None


class SeldruneGPTResponse(BaseModel):
    model: str
    response: str
    response_id: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int
    provider: str


@router.post("/{organization_id}/gpt", response_model=SeldruneGPTResponse)
def seldrune_gpt(
    organization_id: UUID,
    payload: SeldruneGPTRequest,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> SeldruneGPTResponse:
    if settings.model_provider != "openai":
        raise HTTPException(status_code=503, detail="OpenAI model provider is not enabled")
    history = list(
        session.scalars(
            select(SeldruneGPTMessage)
            .where(
                SeldruneGPTMessage.organization_id == organization_id,
                SeldruneGPTMessage.user_id == current_user.id,
            )
            .order_by(SeldruneGPTMessage.created_at.desc())
            .limit(12)
        )
    )
    history.reverse()
    context_lines = [f"{item.role}: {item.content}" for item in history]\n    while sum(len(line) for line in context_lines) > 24000 and context_lines:\n        context_lines.pop(0)\n    context = "\\n".join(context_lines)
    input_text = payload.message
    if context:
        input_text = f"Recent conversation:\\n{context}\\n\\nUser: {payload.message}"
    request = ModelRequest(
        provider=ModelProvider.OPENAI,
        model=settings.model_default,
        input_text=input_text,
        instructions=(
            "You are Seldrune GPT, the reasoning interface inside the Seldrune STI "
            "owner console. Help the owner analyze, design, and plan work. Do not claim "
            f"The configured model identifier is {settings.model_default}. "
            "When asked which model Seldrune is using, report that configured identifier exactly. "
            "Seldrune STI is an AI-native governed virtual organization: it plans work, "
            "coordinates agents and tools, records evidence, and preserves owner-controlled "
            "approvals. Do not claim "
            "an external action occurred unless Seldrune provides verified evidence."
        ),
        max_output_tokens=settings.model_max_output_tokens,
    )
    try:
        result, _latency_ms = ModelGateway(settings).generate(request)
    except ModelGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="user",
            content=payload.message,
        )
    )
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="assistant",
            content=result.output_text,
            model=result.model,
            response_id=result.response_id,
        )
    )
    session.commit()
    return SeldruneGPTResponse(
        model=result.model,
        response=result.output_text,
        response_id=result.response_id,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        latency_ms=int(_latency_ms),
        provider=settings.model_provider,
    )
