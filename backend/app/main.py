from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes.agent_revisions import router as agent_revisions_router
from backend.app.api.routes.agent_tasks import router as agent_tasks_router
from backend.app.api.routes.aetherion import router as aetherion_router
from backend.app.api.routes.audit import router as audit_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.billing import router as billing_router
from backend.app.api.routes.console import router as console_router
from backend.app.api.routes.email_verification import router as email_verification_router
from backend.app.api.routes.executive_brief import router as executive_brief_router
from backend.app.api.routes.knowledge import router as knowledge_router\nfrom backend.app.api.routes.life import router as life_router
from backend.app.api.routes.membership_admin import router as membership_admin_router
from backend.app.api.routes.mfa import router as mfa_router
from backend.app.api.routes.orchestrations import router as orchestrations_router
from backend.app.api.routes.organization_kernel import router as organization_kernel_router
from backend.app.api.routes.organizations import router as organizations_router
from backend.app.api.routes.owner_attention import router as owner_attention_router
from backend.app.api.routes.owner_commands import router as owner_commands_router
from backend.app.api.routes.owner_push import router as owner_push_router
from backend.app.api.routes.research import router as research_router
from backend.app.api.routes.runtime import router as runtime_router
from backend.app.api.routes.secret_references import router as secret_references_router
from backend.app.api.routes.security_events import router as security_events_router
from backend.app.api.routes.sense import router as sense_router
from backend.app.api.routes.status import router as status_router
from backend.app.api.routes.sti import router as sti_router
from backend.app.api.routes.tools import router as tools_router
from backend.app.api.routes.webhooks import router as webhooks_router
from backend.app.core.config import settings

WEB_ROOT = Path(__file__).resolve().parent / "web"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
    )
    app.include_router(console_router)
    app.mount("/console-assets", StaticFiles(directory=WEB_ROOT), name="console-assets")
    for item in (
        status_router,
        aetherion_router,
        sti_router,
        auth_router,
        email_verification_router,
        mfa_router,
        organizations_router,
        membership_admin_router,
        organization_kernel_router,
        executive_brief_router,
        owner_attention_router,
        owner_push_router,
        agent_tasks_router,
        agent_revisions_router,
        orchestrations_router,
        sense_router,
        owner_commands_router,
        runtime_router,
        tools_router,
        knowledge_router,\n        life_router,
        secret_references_router,
        security_events_router,
        research_router,
        webhooks_router,
        audit_router,
        billing_router,
    ):
        app.include_router(item, prefix=settings.api_v1_prefix)
    return app


app = create_app()
