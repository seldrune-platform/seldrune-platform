import os
import secrets
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from backend.app.api.dependencies import SessionDep
from backend.app.core.config import settings
from backend.app.core.tasking import TaskStatus
from backend.app.models.agent import Agent
from backend.app.models.task import Task
from backend.app.services.agent_runtime import AgentRuntimeError, execute_agent_task

router = APIRouter(tags=["status"])
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_PRODUCTION_ENVIRONMENTS = {"prod", "production"}
_ASTRA_BRIDGE_ORG_ID = UUID("8a0bd04d-914d-4481-a94d-050b21f5d9f5")
_astra_bridge_used = False
_ASTRA_RUNPOD_OBJECTIVE = """
Continue the previous Seldrune Architecture Agent GPT-6 Astra RunPod review.

Already established:
- Preferred path: existing Owner Console -> governed Seldrune agents/provider tools -> RunPod.
- Step 1: record bounded deployment/test approval with GPU/spend/test/SLO limits.
- Step 2: use RunPod list/get for read-only authentication and account/resource-scope evidence.
- Step 3 began: inspect the repository for the Live Media image, startup contract,
  GPU requirements, and health endpoint.

Return ONLY the unfinished portion, starting at Step 3. Complete Steps 3-6 with:
- the responsible existing Seldrune agent/tool,
- the exact action,
- an explicit acceptance/evidence gate,
- RunPod pod/endpoint readiness,
- Live Media worker health,
- transformed-frame proof and p95 latency evidence,
- cost limits and cleanup,
- any owner-only blocker.

Keep the answer compact enough to finish. Do not repeat Steps 1-2 except where a dependency
must be referenced. Do not perform external actions and do not invent credentials, resource
IDs, test results, or readiness claims.
""".strip()


@lru_cache
def _expected_schema_revision() -> str | None:
    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


def _release_provenance() -> dict[str, str | None]:
    candidates = (
        ("seldrune", settings.release_sha),
        ("render", os.getenv("RENDER_GIT_COMMIT")),
        ("github", os.getenv("GITHUB_SHA")),
    )
    for source, value in candidates:
        normalized = (value or "").strip()
        if normalized:
            return {"sha": normalized, "source": source}
    return {"sha": None, "source": None}


def _schema_check(session: SessionDep) -> dict[str, Any]:
    expected_revision: str | None = None
    expected_error: str | None = None
    try:
        expected_revision = _expected_schema_revision()
    except Exception as exc:
        expected_error = type(exc).__name__

    current_revision: str | None = None
    current_error: str | None = None
    try:
        current_revision = session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    except Exception as exc:
        session.rollback()
        current_error = type(exc).__name__

    schema_current = (
        expected_revision is not None
        and current_revision is not None
        and current_revision == expected_revision
    )
    if schema_current:
        check_status = "ok"
    elif current_error is not None or expected_error is not None:
        check_status = "unavailable"
    else:
        check_status = "mismatch"

    return {
        "status": check_status,
        "schema_current": schema_current,
        "current_revision": current_revision,
        "expected_revision": expected_revision,
        "required": settings.environment.lower() in _PRODUCTION_ENVIRONMENTS,
        **({"current_error": current_error} if current_error else {}),
        **({"expected_error": expected_error} if expected_error else {}),
    }


def _status_payload(session: SessionDep) -> dict[str, Any]:
    database_healthy = True
    database_error: str | None = None
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        session.rollback()
        database_healthy = False
        database_error = type(exc).__name__

    schema = _schema_check(session) if database_healthy else {
        "status": "unavailable",
        "schema_current": False,
        "current_revision": None,
        "expected_revision": _expected_schema_revision(),
        "required": settings.environment.lower() in _PRODUCTION_ENVIRONMENTS,
        "current_error": database_error,
    }
    if settings.model_provider == "mock":
        provider_configured = True
    elif settings.model_provider == "openai":
        provider_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    elif settings.model_provider == "openai_compatible":
        provider_configured = bool(
            (settings.model_compatible_base_url or "").strip()
        )
    else:
        provider_configured = False
    schema_ready = not schema["required"] or schema["schema_current"]
    ready = database_healthy and provider_configured and schema_ready
    checks: dict[str, Any] = {
        "database": {
            "status": "ok" if database_healthy else "error",
            **({"error": database_error} if database_error else {}),
        },
        "schema": schema,
        "model_provider": {
            "status": "ok" if provider_configured else "unconfigured",
            "provider": settings.model_provider,
            "model": settings.model_default,
            "live_ai": (
                settings.model_provider in {"openai", "openai_compatible"}
                and provider_configured
            ),
        },
    }
    return {
        "status": "ready" if ready else "degraded",
        "ready": ready,
        "service": "seldrune-platform",
        "version": settings.app_version,
        "environment": settings.environment,
        "release": _release_provenance(),
        "checked_at": datetime.now(UTC).isoformat(),
        "checks": checks,
    }


@router.get("/status")
def service_status(session: SessionDep) -> dict[str, Any]:
    return _status_payload(session)


@router.get("/ready")
def service_readiness(session: SessionDep) -> JSONResponse:
    payload = _status_payload(session)
    return JSONResponse(
        status_code=200 if payload["ready"] else 503,
        content=payload,
    )


@router.get("/internal/astra-runpod-review")
def temporary_astra_runpod_review(token: str, session: SessionDep) -> dict[str, Any]:
    """Temporary, disabled-by-default bridge for one governed Astra architecture review."""
    global _astra_bridge_used

    enabled = os.getenv("SELDRUNE_ASTRA_BRIDGE_ENABLED", "").strip() == "1"
    expected_token = os.getenv("SELDRUNE_ASTRA_BRIDGE_TOKEN", "").strip()
    if (
        not enabled
        or not expected_token
        or _astra_bridge_used
        or not secrets.compare_digest(token, expected_token)
    ):
        raise HTTPException(status_code=404, detail="Not found")

    agent = session.scalar(
        select(Agent)
        .where(
            Agent.organization_id == _ASTRA_BRIDGE_ORG_ID,
            Agent.slug == "seldrune-architecture",
        )
        .limit(1)
    )
    if agent is None or agent.created_by_user_id is None:
        raise HTTPException(status_code=503, detail="Architecture Agent is unavailable")

    task = Task(
        organization_id=_ASTRA_BRIDGE_ORG_ID,
        created_by_user_id=agent.created_by_user_id,
        assigned_agent_id=agent.id,
        title="GPT-6 Astra RunPod architecture review continuation",
        objective=_ASTRA_RUNPOD_OBJECTIVE,
        priority=10,
        status=TaskStatus.ASSIGNED.value,
        input_data={
            "source": "temporary_astra_bridge",
            "requested_model": "gpt-6-astra",
            "external_actions_allowed": False,
        },
    )
    session.add(task)
    session.flush()

    runtime_agent = SimpleNamespace(
        id=agent.id,
        name=agent.name,
        slug=agent.slug,
        status=agent.status,
        version=agent.version,
        capabilities=agent.capabilities,
        runtime_config={
            **(agent.runtime_config or {}),
            "provider": "openai",
            "model": "gpt-6-astra",
            "max_output_tokens": 450,
            "input_cost_per_million": 10.0,
            "output_cost_per_million": 50.0,
        },
        allowed_model_providers=["openai"],
        allowed_models=["gpt-6-astra"],
        allowed_tool_slugs=agent.allowed_tool_slugs,
    )

    try:
        completed = execute_agent_task(
            session,
            task=task,
            agent=runtime_agent,
            actor_user_id=agent.created_by_user_id,
        )
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Astra review failed: {exc}") from exc

    _astra_bridge_used = True
    output = completed.output_data or {}
    return {
        "task_id": str(completed.id),
        "status": completed.status,
        "agent": agent.name,
        "provider": output.get("provider"),
        "model": output.get("model"),
        "response_id": output.get("response_id"),
        "usage": output.get("usage"),
        "response": output.get("text"),
    }
