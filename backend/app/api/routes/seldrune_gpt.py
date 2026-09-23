import base64
import binascii
import json
import re

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from pydantic import BaseModel, Field

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.api.routes.orchestrations import _get_run
from backend.app.api.routes.owner_commands import (
    approve_owner_command,
    create_owner_command,
    execute_owner_command,
    get_owner_command_brief,
)
from backend.app.core.config import settings
from backend.app.core.modeling import ModelFileInput, ModelImageInput, ModelProvider, ModelRequest
from backend.app.core.rbac import Permission, Role
from backend.app.models.membership import Membership
from backend.app.models.orchestration import OrchestrationStep
from backend.app.models.seldrune_gpt_message import SeldruneGPTMessage
from backend.app.models.task import Task
from backend.app.models.tool_definition import ToolDefinition
from backend.app.schemas.orchestration import AutonomousExecutionRequest, OrchestrationCreate
from backend.app.services.ai_cost_governor import apply_budget_pressure, choose_cost_route
from backend.app.services.ai_media_budget import build_media_cost_policy
from backend.app.services.ai_spend_guard import (
    AISpendBudgetExceeded,
    ai_spend_budget_status,
    enforce_ai_spend_budget,
)
from backend.app.services.audit import record_audit
from backend.app.services.external_actions import default_external_action_catalog
from backend.app.services.model_gateway import ModelGateway, ModelGatewayError
from backend.app.services.owner_action_compiler import required_external_tool_actions
from backend.app.services.pdf_editor import (
    PDFEditorError,
    apply_pdf_edit_plan,
    assess_pdf_edit_candidate,
    inspect_pdf,
    prepare_pdf_for_model,
    render_pdf_pages_for_model,
    validate_pdf_edit_plan,
)
from backend.app.services.seldrune_pdf_brain import (
    training_summary as pdf_brain_training_summary,
    try_local_pdf_edit,
)
from backend.app.services.tool_bootstrap import (
    configured_external_tool_status,
    ensure_configured_external_tools,
)

router = APIRouter(prefix="/organizations", tags=["seldrune-gpt"])
run_dependency = require_org_permission(Permission.AGENTS_RUN)
AgentsRunDep = Annotated[Membership, Depends(run_dependency)]
OwnerOperatorDep = Annotated[
    Membership,
    Depends(require_org_permission(Permission.ORG_MANAGE)),
]


_OPERATOR_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "destructive_change",
        re.compile(r"\b(delete|erase|wipe|drop|destroy)\b", re.I),
    ),
    (
        "financial_commitment",
        re.compile(
            r"\b(pay|purchase|buy|subscribe|spend|transfer|refund|invoice)\b",
            re.I,
        ),
    ),
    (
        "credential_or_access_change",
        re.compile(
            r"\b(password|credential|secret|api[ -]?key|token|mfa|permission|access)\b",
            re.I,
        ),
    ),
    (
        "legal_or_people_commitment",
        re.compile(
            r"\b(sign|contract|hire|fire|terminate employment|legal filing)\b",
            re.I,
        ),
    ),
    (
        "repository_merge",
        re.compile(
            r"\bmerge\b.{0,80}\b(pull request|pr)\b"
            r"|\b(pull request|pr)\b.{0,80}\bmerge\b",
            re.I,
        ),
    ),
)


def _operator_risk_reasons(order: str) -> list[str]:
    return [name for name, pattern in _OPERATOR_RISK_PATTERNS if pattern.search(order)]


def _missing_external_tools(
    session: SessionDep,
    *,
    organization_id: UUID,
    order: str,
) -> tuple[list[str], list[str]]:
    required = required_external_tool_actions(order)
    if not required:
        return [], []

    active = {
        (tool.provider, tool.action_name)
        for tool in session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == "active",
            )
        )
    }
    missing = [item for item in required if item not in active]
    if not missing:
        return [], []

    catalog = {
        (str(item["provider"]), str(item["action_name"])): item
        for item in default_external_action_catalog()
    }
    missing_tools = [f"{provider}:{action_name}" for provider, action_name in missing]
    env_locators = sorted(
        {
            str(catalog[item]["credential_env_locator"])
            for item in missing
            if item in catalog
        }
    )
    return missing_tools, env_locators


def _planned_external_tool_actions(
    session: SessionDep,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> set[tuple[str, str]]:
    tool_slugs: set[str] = set()
    tasks = session.scalars(
        select(Task)
        .join(OrchestrationStep, OrchestrationStep.task_id == Task.id)
        .where(
            OrchestrationStep.orchestration_run_id == run_id,
            Task.organization_id == organization_id,
        )
    )
    for task in tasks:
        request = (task.input_data or {}).get("tool_request")
        if isinstance(request, dict):
            slug = request.get("slug")
            if isinstance(slug, str) and slug:
                tool_slugs.add(slug)
    if not tool_slugs:
        return set()
    return {
        (tool.provider, tool.action_name)
        for tool in session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.slug.in_(tool_slugs),
            )
        )
    }


def _require_owner_role(membership: Membership) -> None:
    if membership.role != Role.OWNER.value:
        raise HTTPException(status_code=403, detail="Owner role required")


class SeldruneGPTAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    media_type: str = Field(min_length=3, max_length=160)
    data_base64: str = Field(min_length=1, max_length=40_000_000)


class SeldruneGPTRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    attachments: list[SeldruneGPTAttachment] = Field(default_factory=list, max_length=6)


_IMAGE_MEDIA_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
_FILE_MEDIA_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
_MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
_MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024


def _model_attachments(
    attachments: list[SeldruneGPTAttachment],
) -> tuple[tuple[ModelImageInput, ...], tuple[ModelFileInput, ...], list[str]]:
    images: list[ModelImageInput] = []
    files: list[ModelFileInput] = []
    names: list[str] = []
    total_bytes = 0
    for attachment in attachments:
        media_type = attachment.media_type.lower().strip()
        if media_type not in _IMAGE_MEDIA_TYPES | _FILE_MEDIA_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported GPT attachment type: {attachment.media_type}",
            )
        try:
            decoded = base64.b64decode(attachment.data_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail="Invalid attachment encoding") from exc
        size = len(decoded)
        if size > _MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Attachment {attachment.name} exceeds 8 MB",
            )
        total_bytes += size
        if total_bytes > _MAX_TOTAL_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail="GPT attachments exceed 20 MB total")
        names.append(attachment.name)
        if media_type in _IMAGE_MEDIA_TYPES:
            images.append(
                ModelImageInput(
                    media_type=media_type,
                    data_base64=attachment.data_base64,
                    name=attachment.name,
                )
            )
        else:
            files.append(
                ModelFileInput(
                    filename=attachment.name,
                    media_type=media_type,
                    data_base64=attachment.data_base64,
                )
            )
    return tuple(images), tuple(files), names


class SeldruneGPTPDFEditRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=12000)
    pdf: SeldruneGPTAttachment
    password: str | None = Field(default=None, max_length=256)


class SeldruneGPTPDFEditResponse(BaseModel):
    filename: str
    data_base64: str
    summary: str
    applied_edits: int
    warnings: list[str] = Field(default_factory=list)
    model: str
    response_id: str | None = None
    document_type: str
    page_count: int
    native_text_pages: int
    image_only_pages: int
    form_fields: int
    verified_operations: int
    verification_score: int
    visual_fidelity_score: int | None
    layout_integrity_score: int
    reconstruction_attempts: int = 1
    repair_passes: int = 0
    estimated_ai_cost_usd: float | None = None
    model_calls: int = 0
    models_used: list[str] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)


_PDF_EDIT_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "operations": {
            "type": "array",
            "maxItems": 80,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "replace_text",
                            "redact_text",
                            "add_text",
                            "add_note",
                            "fill_form",
                            "rotate_page",
                        ],
                    },
                    "page": {"type": ["integer", "null"], "minimum": 1},
                    "target_text": {"type": ["string", "null"]},
                    "replacement_text": {"type": ["string", "null"]},
                    "text": {"type": ["string", "null"]},
                    "bbox": {
                        "type": ["array", "null"],
                        "items": {"type": "number", "minimum": 0, "maximum": 1000},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "occurrence": {"type": ["integer", "null"], "minimum": 1},
                    "field_name": {"type": ["string", "null"]},
                    "value": {"type": ["string", "null"]},
                    "degrees": {"type": ["integer", "null"]},
                    "font_size": {"type": ["number", "null"], "minimum": 4, "maximum": 144},
                    "font_family_hint": {"type": ["string", "null"]},
                    "font_weight": {
                        "type": ["string", "null"],
                        "enum": ["regular", "bold", None],
                    },
                    "font_style": {
                        "type": ["string", "null"],
                        "enum": ["regular", "italic", None],
                    },
                    "alignment": {
                        "type": ["string", "null"],
                        "enum": ["left", "center", "right", None],
                    },
                    "text_color": {
                        "type": ["array", "null"],
                        "items": {"type": "number", "minimum": 0, "maximum": 1},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                    "background_color": {
                        "type": ["array", "null"],
                        "items": {"type": "number", "minimum": 0, "maximum": 1},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                },
                "required": [
                    "action",
                    "page",
                    "target_text",
                    "replacement_text",
                    "text",
                    "bbox",
                    "occurrence",
                    "field_name",
                    "value",
                    "degrees",
                    "font_size",
                    "font_family_hint",
                    "font_weight",
                    "font_style",
                    "alignment",
                    "text_color",
                    "background_color",
                ],
            },
        },
    },
    "required": ["summary", "operations"],
}


def _apply_pdf_edit_plan(
    pdf_bytes: bytes,
    plan: dict,
    *,
    password: str | None = None,
) -> tuple[bytes, int, list[str]]:
    try:
        result = apply_pdf_edit_plan(
            pdf_bytes,
            plan,
            password=password,
        )
    except PDFEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.data, result.applied_edits, result.warnings


_PDF_VISION_DIAGNOSTIC_MARKERS = (
    "was not found",
    "could not be located",
    "could not be verified near its bbox",
    "not detectable near",
    "visual-region",
    "precise bbox",
)


def _pdf_retry_visual_pages(
    plan: dict,
    diagnostics: list[str],
    *,
    page_count: int,
    max_pages: int = 3,
) -> tuple[int, ...]:
    relevant_operations: set[int] = set()
    needs_visual_fallback = False
    for diagnostic in diagnostics:
        normalized = diagnostic.casefold()
        if not any(marker in normalized for marker in _PDF_VISION_DIAGNOSTIC_MARKERS):
            continue
        needs_visual_fallback = True
        match = re.search(r"\boperation\s+(\d+)\b", normalized)
        if match:
            relevant_operations.add(int(match.group(1)))

    if not needs_visual_fallback:
        return ()

    operations = plan.get("operations")
    if not isinstance(operations, list):
        operations = []

    referenced_pages: list[int] = []
    for op_index, operation in enumerate(operations, start=1):
        if relevant_operations and op_index not in relevant_operations:
            continue
        if not isinstance(operation, dict):
            continue
        page_number = operation.get("page")
        if (
            isinstance(page_number, int)
            and 1 <= page_number <= page_count
            and page_number not in referenced_pages
        ):
            referenced_pages.append(page_number)

    if not referenced_pages and relevant_operations:
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            page_number = operation.get("page")
            if (
                isinstance(page_number, int)
                and 1 <= page_number <= page_count
                and page_number not in referenced_pages
            ):
                referenced_pages.append(page_number)

    if not referenced_pages and page_count > 0:
        referenced_pages = [1]

    return tuple(referenced_pages[: max(1, max_pages)])


class SeldruneGPTOperatorRequest(BaseModel):
    order: str = Field(min_length=5, max_length=8000)
    command_id: UUID | None = None
    confirm_sensitive_action: bool = False
    stop_on_failure: bool = True
    max_steps: int = Field(default=50, ge=1, le=100)
    max_retries_per_step: int = Field(default=1, ge=0, le=2)


class SeldruneGPTOperatorResponse(BaseModel):
    status: Literal[
        "completed",
        "partial",
        "approval_required",
        "configuration_required",
        "failed",
    ]
    command_id: UUID | None = None
    objective: str
    approval_required: bool
    risk_reasons: list[str]
    run_status: str
    executed_steps: int = 0
    failed_steps: int = 0
    blocked_steps: int = 0
    halted_reason: str | None = None
    evidence_url: str | None = None
    missing_tools: list[str] = Field(default_factory=list)
    configuration_hints: list[str] = Field(default_factory=list)
    cost_policy: dict = Field(default_factory=dict)
    brief: dict | None = None


class SeldruneGPTCapabilitiesResponse(BaseModel):
    mode: str
    execution: str
    supported_controls: list[str]
    approval_required_for: list[str]
    evidence: str
    registered_tools: list[str] = Field(default_factory=list)
    provider_readiness: dict[str, bool] = Field(default_factory=dict)
    configuration_hints: list[str] = Field(default_factory=list)


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
    cached_input_tokens: int = 0
    estimated_cost_usd: float | None = None
    cost_tier: str = "configured"
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
    input_images, input_files, attachment_names = _model_attachments(
        payload.attachments
    )
    history = list(
        session.scalars(
            select(SeldruneGPTMessage)
            .where(
                SeldruneGPTMessage.organization_id == organization_id,
                SeldruneGPTMessage.user_id == current_user.id,
            )
            .order_by(SeldruneGPTMessage.created_at.desc())
            .limit(8)
        )
    )
    history.reverse()
    context_lines = [f"{item.role}: {item.content}" for item in history]
    while sum(len(line) for line in context_lines) > 12000 and context_lines:
        context_lines.pop(0)
    context = "\\n".join(context_lines)
    attachment_context = (
        "\\nAttachments in this turn: " + ", ".join(attachment_names)
        if attachment_names
        else ""
    )
    input_text = payload.message + attachment_context
    if context:
        input_text = (
            f"Recent conversation:\\n{context}\\n\\n"
            f"User: {payload.message}{attachment_context}"
        )
    ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    session.commit()
    active_tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == "active",
            )
        )
    )
    bootstrap = configured_external_tool_status(
        session,
        organization_id=organization_id,
    )
    registered_tool_slugs = sorted(tool.slug for tool in active_tools)
    missing_provider_env = sorted(
        {
            provider["credential_env_locator"]
            for provider in bootstrap["providers"]
            if not provider["secret_available"]
        }
    )
    tool_runtime_context = (
        "Registered executable tool slugs: "
        + (", ".join(registered_tool_slugs) if registered_tool_slugs else "none")
        + ". Missing provider configuration: "
        + (", ".join(missing_provider_env) if missing_provider_env else "none")
        + "."
    )
    spend_status = ai_spend_budget_status(
        session,
        organization_id=organization_id,
        settings=settings,
    )
    route = apply_budget_pressure(
        settings,
        choose_cost_route(
            settings,
            purpose="chat",
            text=payload.message,
            has_images=bool(input_images),
            has_files=bool(input_files),
        ),
        monthly_utilization=float(spend_status["monthly_utilization"]),
    )
    try:
        enforce_ai_spend_budget(
            session,
            organization_id=organization_id,
            settings=settings,
            projected_usd=route.request_budget_usd,
        )
    except AISpendBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    request = ModelRequest(
        provider=ModelProvider.OPENAI,
        model=route.model,
        input_text=input_text,
        instructions=(
            "You are Seldrune GPT, the reasoning interface inside the Seldrune STI "
            "owner console. Help the owner analyze, design, and plan work. "
            f"The model selected for this request is {route.model}. "
            "When asked which model is serving the current request, report that identifier "
            "exactly. Seldrune uses an automatic cost governor, so different requests can "
            "use different model tiers. Seldrune STI is an AI-native governed virtual "
            "organization: it plans work, coordinates agents and tools, records evidence, "
            "and preserves owner-controlled approvals. When the owner asks you to perform "
            "work, explain that Execute order can run the instruction through Seldrune's "
            "governed operator. Never imply that chat text alone performed an action. Do "
            "not claim an external action occurred unless Seldrune provides verified "
            "evidence. "
            + tool_runtime_context
        ),
        max_output_tokens=route.max_output_tokens,
        input_images=input_images,
        input_files=input_files,
        image_detail=route.image_detail,
        pdf_detail=route.pdf_detail,
        reasoning_effort=route.reasoning_effort,
        prompt_cache_key=f"seldrune:{organization_id}:gpt",
        max_estimated_cost_usd=route.request_budget_usd,
        exact_token_preflight=(
            bool(input_images or input_files) or len(input_text) > 8000
        ),
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
            content=(
                payload.message
                + (
                    "\\n[Attachments: " + ", ".join(attachment_names) + "]"
                    if attachment_names
                    else ""
                )
            ),
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
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cached_input_tokens=result.usage.cached_input_tokens,
            estimated_cost_usd=result.usage.estimated_cost_usd,
            cost_tier=route.tier,
            model_calls=1,
        )
    )
    session.commit()
    return SeldruneGPTResponse(
        model=result.model,
        response=result.output_text,
        response_id=result.response_id,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cached_input_tokens=result.usage.cached_input_tokens,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        cost_tier=route.tier,
        latency_ms=int(_latency_ms),
        provider=settings.model_provider,
    )


@router.post(
    "/{organization_id}/gpt/pdf/edit",
    response_model=SeldruneGPTPDFEditResponse,
)
def edit_seldrune_gpt_pdf(
    organization_id: UUID,
    payload: SeldruneGPTPDFEditRequest,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> SeldruneGPTPDFEditResponse:
    if payload.pdf.media_type.lower().strip() != "application/pdf":
        raise HTTPException(status_code=422, detail="PDF editor accepts one PDF file")

    try:
        pdf_bytes = base64.b64decode(payload.pdf.data_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail="Invalid PDF encoding") from exc

    if len(pdf_bytes) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Advanced PDF editor supports PDFs up to 25 MB",
        )

    try:
        inspection = inspect_pdf(pdf_bytes, payload.password)
    except PDFEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    local_edit = None
    if settings.pdf_brain_enabled:
        local_edit = try_local_pdf_edit(
            pdf_bytes,
            payload.instruction,
            password=payload.password,
            minimum_confidence=settings.pdf_brain_min_confidence,
            allow_ocr=settings.pdf_local_ocr_enabled,
        )

    if local_edit is not None:
        edit_result = local_edit.result
        selected_assessment = local_edit.assessment
        plan = local_edit.prediction.plan or {}
        stem = payload.pdf.name.rsplit(".", 1)[0]
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._") or "document"
        output_name = f"{safe_stem}-edited.pdf"
        summary = str(plan.get("summary") or "PDF edit completed locally.")
        visual_summary = (
            f"{edit_result.visual_fidelity_score}% visual fidelity"
            if edit_result.visual_fidelity_score is not None
            else "visual fidelity not machine-scored for this PDF type"
        )
        local_model = local_edit.prediction.model_version
        local_response_id = f"local:{local_edit.prediction.model_fingerprint}"

        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="seldrune_gpt.pdf_edited",
            resource_type="document",
            resource_id=output_name,
            details={
                "source_filename": payload.pdf.name,
                "output_filename": output_name,
                "document_type": edit_result.inspection.document_type,
                "page_count": edit_result.inspection.page_count,
                "applied_edits": edit_result.applied_edits,
                "verified_operations": edit_result.verified_operations,
                "verification_score": edit_result.verification_score,
                "visual_fidelity_score": edit_result.visual_fidelity_score,
                "layout_integrity_score": selected_assessment.layout_integrity_score,
                "reconstruction_attempts": 1,
                "repair_passes": 0,
                "warnings": edit_result.warnings[:20],
                "model": local_model,
                "models_used": [local_model],
                "model_calls": 0,
                "estimated_ai_cost_usd": 0.0,
                "planner": "seldrune_owned_local",
                "local_intent": local_edit.prediction.intent,
                "local_confidence": round(local_edit.prediction.confidence, 6),
                "model_fingerprint": local_edit.prediction.model_fingerprint,
                "local_ocr_used": local_edit.ocr_used,
            },
        )
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="user",
                content=f"{payload.instruction}\n[Local PDF edit: {payload.pdf.name}]",
            )
        )
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="assistant",
                content=(
                    f"{summary} Created {output_name} locally with "
                    f"{edit_result.applied_edits} applied edits and "
                    f"{edit_result.verification_score}% content verification, "
                    f"{visual_summary}, and "
                    f"{selected_assessment.layout_integrity_score}% layout integrity. "
                    + (
                        "Local CPU OCR was used. "
                        if local_edit.ocr_used
                        else ""
                    )
                    + "No external AI model call was required."
                ),
                model=local_model,
                response_id=local_response_id,
                input_tokens=0,
                output_tokens=0,
                cached_input_tokens=0,
                estimated_cost_usd=0.0,
                cost_tier="local-owned",
                model_calls=0,
            )
        )
        session.commit()
        return SeldruneGPTPDFEditResponse(
            filename=output_name,
            data_base64=base64.b64encode(edit_result.data).decode("ascii"),
            summary=summary,
            applied_edits=edit_result.applied_edits,
            warnings=edit_result.warnings,
            model=local_model,
            response_id=local_response_id,
            document_type=edit_result.inspection.document_type,
            page_count=edit_result.inspection.page_count,
            native_text_pages=edit_result.inspection.native_text_pages,
            image_only_pages=edit_result.inspection.image_only_pages,
            form_fields=edit_result.inspection.form_fields,
            verified_operations=edit_result.verified_operations,
            verification_score=edit_result.verification_score,
            visual_fidelity_score=edit_result.visual_fidelity_score,
            layout_integrity_score=selected_assessment.layout_integrity_score,
            reconstruction_attempts=1,
            repair_passes=0,
            estimated_ai_cost_usd=0.0,
            model_calls=0,
            models_used=[local_model],
            verification_notes=edit_result.verification_notes,
        )

    if not settings.pdf_external_fallback_enabled:
        raise HTTPException(
            status_code=422,
            detail=(
                "Seldrune PDF Brain could not safely resolve this edit locally. "
                "Zero-credit PDF mode is enabled, so Seldrune did not call OpenAI. "
                "Use a more explicit instruction with the exact old and new text, "
                "and include the page number when the value appears more than once."
            ),
        )

    if settings.model_provider != "openai":
        raise HTTPException(
            status_code=503,
            detail=(
                "Seldrune PDF Brain could not safely resolve this edit locally and "
                "OpenAI fallback is not enabled."
            ),
        )

    try:
        model_pdf_bytes = prepare_pdf_for_model(pdf_bytes, payload.password)
    except PDFEditorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    input_files = (
        ModelFileInput(
            filename=payload.pdf.name,
            media_type="application/pdf",
            data_base64=base64.b64encode(model_pdf_bytes).decode("ascii"),
        ),
    )
    profile = (
        f"PDF profile: {inspection.page_count} pages; "
        f"type={inspection.document_type}; "
        f"native_text_pages={inspection.native_text_pages}; "
        f"image_only_pages={inspection.image_only_pages}; "
        f"form_fields={inspection.form_fields}."
    )
    spend_status = ai_spend_budget_status(
        session,
        organization_id=organization_id,
        settings=settings,
    )
    pdf_route = apply_budget_pressure(
        settings,
        choose_cost_route(
            settings,
            purpose="pdf",
            text=payload.instruction,
            attempt=0,
            has_images=False,
            has_files=True,
        ),
        monthly_utilization=float(spend_status["monthly_utilization"]),
    )
    try:
        enforce_ai_spend_budget(
            session,
            organization_id=organization_id,
            settings=settings,
            projected_usd=settings.ai_pdf_max_total_usd,
        )
    except AISpendBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    request = ModelRequest(
        provider=ModelProvider.OPENAI,
        model=pdf_route.model,
        input_text=(
            "Edit the attached PDF according to this owner instruction:\n"
            f"{payload.instruction}\n\n{profile}\n"
            "Use the attached PDF itself for the first-pass plan. Prefer native text and "
            "do not invent coordinates when a requested target is not searchable. If an "
            "exact visual bbox cannot be established confidently, keep the target page and "
            "text precise and leave bbox null so a targeted visual retry can localize only "
            "the affected page."
        ),
        instructions=(
            "You are Seldrune's autonomous AI PDF editor. Follow the owner's requested "
            "document changes directly and translate plain-language intent into the required "
            "PDF operations without asking the owner for coordinates, field names, font "
            "settings, or editing mechanics. Preserve content the owner did not ask to "
            "change. Use page numbers starting at 1. Prefer replace_text/redact_text for "
            "native text and derive exact target_text from the document. For scanned, "
            "image-only, or visually positioned content, inspect the PDF visually and derive "
            "the normalized 0..1000 bbox yourself. For image/scanned text also infer "
            "font_family_hint, font_weight, font_style, font_size, alignment, text_color, "
            "and background_color from the original visual appearance. Use fill_form when "
            "the target is an "
            "interactive field, add_text/add_note when new visible text is requested, and "
            "rotate_page when rotation is requested. When replacement text is longer than "
            "the original, preserve the owner's exact requested wording and let the editing "
            "engine preserve the original font resource, point size, color, baseline, "
            "alignment, and surrounding layout rather than substituting generic typography. "
            "For repeated values such as 0, salary amounts, dates, IDs, or percentages, "
            "never rely on fuzzy matching: provide the correct occurrence or an exact bbox "
            "for the intended row/cell. Do not create two operations whose target regions "
            "overlap. Resolve "
            "repeated targets from the owner's context and occurrence. Never require a "
            "manual edit plan from the owner."
        ),
        max_output_tokens=pdf_route.max_output_tokens,
        response_schema=_PDF_EDIT_SCHEMA,
        input_images=(),
        input_files=input_files,
        image_detail=pdf_route.image_detail,
        pdf_detail=pdf_route.pdf_detail,
        reasoning_effort=pdf_route.reasoning_effort,
        prompt_cache_key=f"seldrune:{organization_id}:pdf:{payload.pdf.name}",
        max_estimated_cost_usd=pdf_route.request_budget_usd,
        exact_token_preflight=True,
    )
    try:
        result, _latency_ms = ModelGateway(settings).generate(request)
    except ModelGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    total_ai_cost = float(result.usage.estimated_cost_usd or 0.0)
    final_model = result.model
    final_response_id = result.response_id
    total_input_tokens = result.usage.input_tokens
    total_output_tokens = result.usage.output_tokens
    total_cached_input_tokens = result.usage.cached_input_tokens
    model_calls = 1
    models_used: set[str] = {result.model}

    try:
        plan = json.loads(result.output_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Model returned an invalid PDF edit plan",
        ) from exc

    edit_result = None
    selected_assessment = None
    candidate_plan = plan
    reconstruction_attempts = 0
    last_diagnostics: list[str] = []
    best_safe_result = None
    best_safe_assessment = None
    best_safe_plan = None
    best_safe_quality = -1

    for attempt_index in range(settings.ai_pdf_max_attempts):
        reconstruction_attempts = attempt_index + 1
        candidate_result = None
        candidate_assessment = None
        candidate_diagnostics: list[str] = []

        try:
            plan_validation = validate_pdf_edit_plan(
                pdf_bytes,
                candidate_plan,
                password=payload.password,
            )
            if not plan_validation.valid:
                candidate_diagnostics.extend(plan_validation.issues)
            else:
                candidate_result = apply_pdf_edit_plan(
                    pdf_bytes,
                    candidate_plan,
                    password=payload.password,
                )
                candidate_assessment = assess_pdf_edit_candidate(
                    pdf_bytes,
                    candidate_result.data,
                    candidate_plan,
                    password=payload.password,
                    visual_fidelity_score=candidate_result.visual_fidelity_score,
                )
                candidate_diagnostics.extend(candidate_assessment.issues)
                candidate_diagnostics.extend(
                    warning
                    for warning in candidate_result.warnings
                    if "target was not found" in warning
                    or "did not fit cleanly" in warning
                )

                content_verified = (
                    candidate_result.verification_score == 100
                    or inspection.image_only_pages > 0
                )
                if not content_verified:
                    candidate_diagnostics.append(
                        "content verification did not reach the required level"
                    )

                structurally_safe = (
                    candidate_assessment.safe_to_return
                    and content_verified
                    and not candidate_diagnostics
                )
                if structurally_safe:
                    fidelity = candidate_result.visual_fidelity_score
                    quality = fidelity if fidelity is not None else 100
                    if quality > best_safe_quality:
                        best_safe_result = candidate_result
                        best_safe_assessment = candidate_assessment
                        best_safe_plan = candidate_plan
                        best_safe_quality = quality

                    if fidelity is None or fidelity >= 95:
                        edit_result = candidate_result
                        selected_assessment = candidate_assessment
                        plan = candidate_plan
                        break

                    candidate_diagnostics.append(
                        "candidate is structurally safe but original-look fidelity is "
                        f"{fidelity}%; try to improve typography while keeping the same "
                        "target geometry"
                    )
        except PDFEditorError as exc:
            candidate_diagnostics.append(str(exc))

        last_diagnostics = list(dict.fromkeys(candidate_diagnostics))
        if attempt_index >= settings.ai_pdf_max_attempts - 1:
            break
        if total_ai_cost >= settings.ai_pdf_max_total_usd:
            last_diagnostics.append(
                "AI cost governor stopped additional PDF reconstruction attempts "
                f"after USD {total_ai_cost:.4f} estimated spend"
            )
            break

        rejection_text = (
            "\n- ".join(last_diagnostics[:30])
            if last_diagnostics
            else "candidate can be improved"
        )
        retry_visual_page_numbers = _pdf_retry_visual_pages(
            candidate_plan,
            last_diagnostics,
            page_count=inspection.page_count,
        )
        retry_page_renders = ()
        if retry_visual_page_numbers:
            try:
                retry_page_renders = render_pdf_pages_for_model(
                    pdf_bytes,
                    payload.password,
                    page_numbers=list(retry_visual_page_numbers),
                    max_pages=len(retry_visual_page_numbers),
                    max_long_edge=1200,
                )
            except PDFEditorError:
                retry_page_renders = ()

        retry_images = tuple(
            ModelImageInput(
                media_type=render.media_type,
                data_base64=base64.b64encode(render.data).decode("ascii"),
                name=f"pdf-page-{render.page_number}.jpg",
            )
            for render in retry_page_renders
        )
        retry_visual_pages = ", ".join(
            str(render.page_number) for render in retry_page_renders
        ) or "none"
        if retry_images:
            retry_visual_instruction = (
                "Rendered ORIGINAL page previews are attached after this text in page "
                f"order: {retry_visual_pages}. For every missing/search-invisible target, "
                "locate it visually in these previews and supply a normalized bbox "
                "[x0,y0,x1,y1] on the 0..1000 coordinate system."
            )
        else:
            retry_visual_instruction = (
                "No extra page previews are attached for this retry because the diagnostics "
                "do not require visual localization. Use the previous plan and diagnostics "
                "to repair only the failed detail without changing unrelated geometry."
            )

        retry_route = apply_budget_pressure(
            settings,
            choose_cost_route(
                settings,
                purpose="pdf",
                text=payload.instruction,
                attempt=attempt_index + 1,
                has_images=bool(retry_images),
                has_files=False,
            ),
            monthly_utilization=float(spend_status["monthly_utilization"]),
        )
        remaining_pdf_budget = max(
            0.001,
            settings.ai_pdf_max_total_usd - total_ai_cost,
        )
        retry_request = ModelRequest(
            provider=ModelProvider.OPENAI,
            model=retry_route.model,
            input_text=(
                "Create a complete replacement edit plan against the ORIGINAL PDF context. "
                "Do not layer on a previous candidate.\n"
                f"Owner instruction: {payload.instruction}\n\n"
                f"Previous candidate diagnostics:\n- {rejection_text}\n\n"
                f"Previous plan JSON:\n{json.dumps(candidate_plan, separators=(',', ':'))}\n\n"
                f"{profile}\n"
                f"{retry_visual_instruction}"
            ),
            instructions=(
                "Re-plan the edit from the untouched original PDF. Every requested change "
                "must be applied exactly once. Do not place replacement text above, below, "
                "or on top of an existing value. For native text, identify the exact original "
                "target and occurrence and let the engine reuse its font, baseline, color, "
                "and alignment. If a value occurs more than once, explicitly choose its "
                "occurrence or give a precise bbox from the original page. Never use fuzzy "
                "numeric targets and never generate overlapping operations. For tables, keep "
                "the replacement inside the same cell and do not cross component labels, "
                "borders, or neighboring values. If the previous candidate was already "
                "structurally safe but had lower typography fidelity, keep its target "
                "geometry and improve only font/style matching. For scanned content, derive "
                "the exact bbox and typography visually. Return a complete new plan, not a "
                "delta or repair plan. Do not change unrelated content."
            ),
            max_output_tokens=retry_route.max_output_tokens,
            response_schema=_PDF_EDIT_SCHEMA,
            input_images=retry_images,
            input_files=(),
            image_detail="high" if retry_images else "low",
            pdf_detail=retry_route.pdf_detail,
            reasoning_effort=retry_route.reasoning_effort,
            prompt_cache_key=(
                f"seldrune:{organization_id}:pdf-repair:{payload.pdf.name}"
            ),
            max_estimated_cost_usd=min(
                retry_route.request_budget_usd,
                remaining_pdf_budget,
            ),
            exact_token_preflight=True,
        )
        try:
            retry_model_result, _retry_latency = ModelGateway(settings).generate(
                retry_request
            )
            model_calls += 1
            models_used.add(retry_model_result.model)
            final_model = retry_model_result.model
            final_response_id = retry_model_result.response_id
            total_ai_cost += float(
                retry_model_result.usage.estimated_cost_usd or 0.0
            )
            total_input_tokens += retry_model_result.usage.input_tokens
            total_output_tokens += retry_model_result.usage.output_tokens
            total_cached_input_tokens += (
                retry_model_result.usage.cached_input_tokens
            )
            candidate_plan = json.loads(retry_model_result.output_text)
        except (ModelGatewayError, json.JSONDecodeError) as exc:
            last_diagnostics.append(f"AI re-planning failed: {exc}")
            if "cost governor" in str(exc).casefold():
                break

    if edit_result is None and best_safe_result is not None:
        edit_result = best_safe_result
        selected_assessment = best_safe_assessment
        plan = best_safe_plan
        fidelity = edit_result.visual_fidelity_score
        if fidelity is not None and fidelity < 95:
            edit_result.warnings.append(
                "Returned the best structurally safe AI edit after "
                f"{reconstruction_attempts} reconstruction attempts. "
                f"Original-look machine fidelity is {fidelity}%, so review typography "
                "if pixel-level matching is critical."
            )

    if edit_result is None or selected_assessment is None:
        detail = (
            "; ".join(last_diagnostics[:8])
            if last_diagnostics
            else "layout integrity could not be verified"
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "AI PDF editor could not produce a layout-safe edited document. "
                "The original PDF was preserved. " + detail
            ),
        )

    repair_passes = max(0, reconstruction_attempts - 1)
    stem = payload.pdf.name.rsplit(".", 1)[0]
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._") or "document"
    output_name = f"{safe_stem}-edited.pdf"
    summary = str(plan.get("summary") or "PDF edit completed.")
    visual_summary = (
        f"{edit_result.visual_fidelity_score}% visual fidelity"
        if edit_result.visual_fidelity_score is not None
        else "visual fidelity not machine-scored for this PDF type"
    )

    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="seldrune_gpt.pdf_edited",
        resource_type="document",
        resource_id=output_name,
        details={
            "source_filename": payload.pdf.name,
            "output_filename": output_name,
            "document_type": edit_result.inspection.document_type,
            "page_count": edit_result.inspection.page_count,
            "applied_edits": edit_result.applied_edits,
            "verified_operations": edit_result.verified_operations,
            "verification_score": edit_result.verification_score,
            "visual_fidelity_score": edit_result.visual_fidelity_score,
            "layout_integrity_score": selected_assessment.layout_integrity_score,
            "reconstruction_attempts": reconstruction_attempts,
            "repair_passes": repair_passes,
            "warnings": edit_result.warnings[:20],
            "model": final_model,
            "models_used": sorted(models_used),
            "model_calls": model_calls,
            "estimated_ai_cost_usd": round(total_ai_cost, 8),
        },
    )
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="user",
            content=f"{payload.instruction}\n[AI PDF edit: {payload.pdf.name}]",
        )
    )
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="assistant",
            content=(
                f"{summary} Created {output_name} with "
                f"{edit_result.applied_edits} applied edits and "
                f"{edit_result.verification_score}% content verification, "
                f"{visual_summary}, and "
                f"{selected_assessment.layout_integrity_score}% layout integrity"
                + (
                    f" after {reconstruction_attempts} reconstruction attempts."
                    if reconstruction_attempts > 1
                    else "."
                )
            ),
            model=final_model,
            response_id=final_response_id,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cached_input_tokens=total_cached_input_tokens,
            estimated_cost_usd=round(total_ai_cost, 8),
            cost_tier="adaptive",
            model_calls=model_calls,
        )
    )
    session.commit()

    return SeldruneGPTPDFEditResponse(
        filename=output_name,
        data_base64=base64.b64encode(edit_result.data).decode("ascii"),
        summary=summary,
        applied_edits=edit_result.applied_edits,
        warnings=edit_result.warnings,
        model=final_model,
        response_id=final_response_id,
        document_type=edit_result.inspection.document_type,
        page_count=edit_result.inspection.page_count,
        native_text_pages=edit_result.inspection.native_text_pages,
        image_only_pages=edit_result.inspection.image_only_pages,
        form_fields=edit_result.inspection.form_fields,
        verified_operations=edit_result.verified_operations,
        verification_score=edit_result.verification_score,
        visual_fidelity_score=edit_result.visual_fidelity_score,
        layout_integrity_score=selected_assessment.layout_integrity_score,
        reconstruction_attempts=reconstruction_attempts,
        repair_passes=repair_passes,
        estimated_ai_cost_usd=round(total_ai_cost, 8),
        model_calls=model_calls,
        models_used=sorted(models_used),
        verification_notes=edit_result.verification_notes,
    )


@router.get(
    "/{organization_id}/gpt/capabilities",
    response_model=SeldruneGPTCapabilitiesResponse,
)
def seldrune_gpt_capabilities(
    organization_id: UUID,
    membership: OwnerOperatorDep,
    session: SessionDep,
) -> SeldruneGPTCapabilitiesResponse:
    _require_owner_role(membership)
    tools = list(
        session.scalars(
            select(ToolDefinition).where(
                ToolDefinition.organization_id == organization_id,
                ToolDefinition.status == "active",
            )
        )
    )
    readiness = configured_external_tool_status(
        session,
        organization_id=organization_id,
    )
    provider_readiness = {
        provider["provider"]: bool(provider["ready"])
        for provider in readiness["providers"]
    }
    configuration_hints = sorted(
        {
            provider["credential_env_locator"]
            for provider in readiness["providers"]
            if not provider["secret_available"]
        }
    )
    spend_status = ai_spend_budget_status(
        session,
        organization_id=organization_id,
        settings=settings,
    )
    media_policy = build_media_cost_policy(
        settings,
        monthly_utilization=float(spend_status["monthly_utilization"]),
    )
    return SeldruneGPTCapabilitiesResponse(
        mode="governed-owner-operator",
        execution=(
            "single-order plan, execute, verify; fresh confirmation for "
            "high-impact commitments"
        ),
        supported_controls=[
            "organization analysis and planning",
            "research and evidence preparation",
            "agent orchestration",
            "tool execution through registered grants",
            "project delivery and recovery",
            "audited command promotion",
        ],
        approval_required_for=[name for name, _pattern in _OPERATOR_RISK_PATTERNS],
        evidence="Every order receives a durable command id, execution report, and audit trail.",
        registered_tools=sorted(tool.slug for tool in tools),
        provider_readiness=provider_readiness,
        configuration_hints=configuration_hints,
        cost_policy={
            "monthly_hard_limit_usd": settings.ai_monthly_max_usd,
            "pdf_brain": {
                **pdf_brain_training_summary(),
                "enabled": settings.pdf_brain_enabled,
                "minimum_confidence": settings.pdf_brain_min_confidence,
                "routing": (
                    "local-only zero-credit"
                    if not settings.pdf_external_fallback_enabled
                    else "local-first with OpenAI fallback"
                ),
                "local_ocr_enabled": settings.pdf_local_ocr_enabled,
                "external_fallback_enabled": settings.pdf_external_fallback_enabled,
                "local_ai_cost_usd": 0.0,
            },
            "daily_limit_usd": settings.ai_daily_max_usd,
            "budget_mode": spend_status["budget_mode"],
            "monthly_remaining_usd": spend_status["monthly_remaining_usd"],
            "default_text_model": settings.model_economy,
            "image": {
                "model": media_policy.image_model,
                "quality": media_policy.image_quality,
                "size": media_policy.image_size,
                "job_max_usd": media_policy.image_job_max_usd,
            },
            "video": {
                "model": media_policy.video_model,
                "resolution": media_policy.video_resolution,
                "default_seconds": media_policy.video_default_seconds,
                "max_seconds": media_policy.video_max_seconds,
                "job_max_usd": media_policy.video_job_max_usd,
                "prefer_batch": media_policy.prefer_batch,
            },
        },
    )


@router.post(
    "/{organization_id}/gpt/operate",
    response_model=SeldruneGPTOperatorResponse,
)
def operate_seldrune_gpt(
    organization_id: UUID,
    payload: SeldruneGPTOperatorRequest,
    membership: OwnerOperatorDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> SeldruneGPTOperatorResponse:
    _require_owner_role(membership)
    ensure_configured_external_tools(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
    )
    missing_tools, configuration_hints = _missing_external_tools(
        session,
        organization_id=organization_id,
        order=payload.order,
    )
    if missing_tools:
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="seldrune_gpt.operator_configuration_required",
            resource_type="organization",
            resource_id=str(organization_id),
            details={
                "missing_tools": missing_tools,
                "configuration_hints": configuration_hints,
            },
        )
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="assistant",
                content=(
                    "Operator configuration required. Missing executable tools: "
                    + ", ".join(missing_tools)
                    + (
                        ". Configure: " + ", ".join(configuration_hints)
                        if configuration_hints
                        else ""
                    )
                ),
                model=settings.model_default,
            )
        )
        session.commit()
        return SeldruneGPTOperatorResponse(
            status="configuration_required",
            command_id=None,
            objective=payload.order,
            approval_required=False,
            risk_reasons=[],
            run_status="not_started",
            halted_reason="required_external_tool_unavailable",
            missing_tools=missing_tools,
            configuration_hints=configuration_hints,
        )

    risk_reasons = _operator_risk_reasons(payload.order)

    if payload.command_id is None:
        created = create_owner_command(
            organization_id,
            OrchestrationCreate(
                objective=payload.order,
                context={
                    "source": "seldrune_gpt_operator",
                    "seldrune_gpt_operator": {
                        "requested_by": str(current_user.id),
                        "risk_reasons": risk_reasons,
                        "confirmation_required": bool(risk_reasons),
                    },
                },
            ),
            membership,
            current_user,
            session,
        )
        run_id = created.id
    else:
        run = _get_run(session, organization_id, payload.command_id)
        operator_context = (run.context or {}).get("seldrune_gpt_operator")
        if not operator_context:
            raise HTTPException(status_code=404, detail="Seldrune GPT operator command not found")
        if run.objective != payload.order:
            raise HTTPException(status_code=409, detail="Order does not match the pending command")
        run_id = run.id

    required_actions = set(required_external_tool_actions(payload.order))
    planned_actions = _planned_external_tool_actions(
        session,
        organization_id=organization_id,
        run_id=run_id,
    )
    missing_planned = sorted(required_actions - planned_actions)
    evidence_url = (
        f"/api/v1/organizations/{organization_id}/owner-commands/{run_id}/brief"
    )
    if missing_planned:
        missing_planned_tools = [
            f"{provider}:{action_name}"
            for provider, action_name in missing_planned
        ]
        unresolved_run = _get_run(session, organization_id, run_id)
        planner_context = (unresolved_run.context or {}).get("planner") or {}
        compiler_context = planner_context.get("deterministic_action_compiler") or {}
        compiler_hints = list(compiler_context.get("configuration_hints") or [])
        unresolved_user_fields = list(
            compiler_context.get("unresolved_user_fields") or []
        )
        configuration_only = bool(compiler_hints) and not unresolved_user_fields
        audit_action = (
            "seldrune_gpt.operator_action_configuration_required"
            if configuration_only
            else "seldrune_gpt.operator_required_tool_not_planned"
        )
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action=audit_action,
            resource_type="orchestration",
            resource_id=str(run_id),
            details={
                "missing_tools": missing_planned_tools,
                "configuration_hints": compiler_hints,
                "unresolved_user_fields": unresolved_user_fields,
            },
        )
        if configuration_only:
            message = (
                "Operator configuration required before execution. Configure: "
                + ", ".join(compiler_hints)
            )
            status_value = "configuration_required"
            halted_reason = "required_external_action_configuration_missing"
        else:
            message = (
                "Operator stopped before execution because required external action "
                "inputs could not be resolved safely: "
                + ", ".join(missing_planned_tools)
            )
            status_value = "failed"
            halted_reason = "required_external_tool_not_planned"
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="assistant",
                content=message,
                model=settings.model_default,
            )
        )
        session.commit()
        run = _get_run(session, organization_id, run_id)
        return SeldruneGPTOperatorResponse(
            status=status_value,
            command_id=run_id,
            objective=payload.order,
            approval_required=False,
            risk_reasons=risk_reasons,
            run_status=run.status,
            halted_reason=halted_reason,
            evidence_url=evidence_url,
            missing_tools=missing_planned_tools,
            configuration_hints=compiler_hints,
        )
    if risk_reasons and not payload.confirm_sensitive_action:
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="seldrune_gpt.operator_approval_required",
            resource_type="orchestration",
            resource_id=str(run_id),
            details={"risk_reasons": risk_reasons},
        )
        session.add(
            SeldruneGPTMessage(
                organization_id=organization_id,
                user_id=current_user.id,
                role="assistant",
                content=(
                    "Operator command created. Explicit owner confirmation is required for: "
                    + ", ".join(risk_reasons)
                ),
                model=settings.model_default,
            )
        )
        session.commit()
        run = _get_run(session, organization_id, run_id)
        return SeldruneGPTOperatorResponse(
            status="approval_required",
            command_id=run_id,
            objective=payload.order,
            approval_required=True,
            risk_reasons=risk_reasons,
            run_status=run.status,
            evidence_url=evidence_url,
        )

    if risk_reasons and payload.confirm_sensitive_action:
        confirmed_run = _get_run(session, organization_id, run_id)
        operator_context = (confirmed_run.context or {}).get("seldrune_gpt_operator") or {}
        confirmed_run.context = {
            **(confirmed_run.context or {}),
            "seldrune_gpt_operator": {
                **operator_context,
                "confirmed": True,
                "confirmed_by": str(current_user.id),
            },
        }
        session.commit()

    approve_owner_command(
        organization_id,
        run_id,
        membership,
        current_user,
        session,
    )
    result = execute_owner_command(
        organization_id,
        run_id,
        AutonomousExecutionRequest(
            stop_on_failure=payload.stop_on_failure,
            max_steps=payload.max_steps,
            max_retries_per_step=payload.max_retries_per_step,
        ),
        membership,
        current_user,
        session,
    )
    report = result.execution
    brief = get_owner_command_brief(
        organization_id,
        run_id,
        membership,
        session,
    )
    if report.failed_steps:
        status_value = "failed"
    elif report.blocked_steps or report.approval_blocked_steps or report.halted_reason:
        status_value = "partial"
    else:
        status_value = "completed"
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action=f"seldrune_gpt.operator_{status_value}",
        resource_type="orchestration",
        resource_id=str(run_id),
        details={
            "risk_reasons": risk_reasons,
            "executed_steps": report.executed_steps,
            "failed_steps": report.failed_steps,
            "blocked_steps": report.blocked_steps,
            "halted_reason": report.halted_reason,
        },
    )
    session.add(
        SeldruneGPTMessage(
            organization_id=organization_id,
            user_id=current_user.id,
            role="assistant",
            content=(
                f"Operator {status_value}: {report.executed_steps} steps executed, "
                f"{report.failed_steps} failed, {report.blocked_steps} blocked. "
                f"Command evidence: {run_id}."
            ),
            model=settings.model_default,
        )
    )
    session.commit()
    return SeldruneGPTOperatorResponse(
        status=status_value,
        command_id=run_id,
        objective=payload.order,
        approval_required=False,
        risk_reasons=risk_reasons,
        run_status=result.run.status,
        executed_steps=report.executed_steps,
        failed_steps=report.failed_steps,
        blocked_steps=report.blocked_steps + report.approval_blocked_steps,
        halted_reason=report.halted_reason,
        evidence_url=evidence_url,
        brief=brief,
    )


@router.get("/{organization_id}/gpt/history", response_model=list[SeldruneGPTHistoryMessage])
def seldrune_gpt_history(
    organization_id: UUID,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[SeldruneGPTHistoryMessage]:
    messages = list(
        session.scalars(
            select(SeldruneGPTMessage)
            .where(
                SeldruneGPTMessage.organization_id == organization_id,
                SeldruneGPTMessage.user_id == current_user.id,
            )
            .order_by(SeldruneGPTMessage.created_at.asc())
            .limit(100)
        )
    )
    return [
        SeldruneGPTHistoryMessage(role=item.role, content=item.content, model=item.model)
        for item in messages
    ]


@router.delete("/{organization_id}/gpt/history", status_code=204)
def clear_seldrune_gpt_history(
    organization_id: UUID,
    _membership: AgentsRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> None:
    session.execute(
        delete(SeldruneGPTMessage).where(
            SeldruneGPTMessage.organization_id == organization_id,
            SeldruneGPTMessage.user_id == current_user.id,
        )
    )
    session.commit()
