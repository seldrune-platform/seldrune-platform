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
from backend.app.api.routes.development_mission import router as development_mission_router
from backend.app.api.routes.email_verification import router as email_verification_router
from backend.app.api.routes.executive_brief import router as executive_brief_router
from backend.app.api.routes.knowledge import router as knowledge_router
from backend.app.api.routes.life import router as life_router
from backend.app.api.routes.mail import (
    oauth_router as mail_oauth_router,
    page_router as mail_page_router,
    router as mail_router,
)
from backend.app.api.routes.liveshift_face import router as liveshift_face_router
from backend.app.api.routes.live_profile_authorizations import (
    internal_router as live_profile_authorizer_internal_router,
    page_router as live_profile_authorizations_page_router,
    router as live_profile_authorizations_router,
)
from backend.app.api.routes.liveshell_mobile import (
    api_router as liveshell_mobile_api_router,
    page_router as liveshell_mobile_page_router,
)
from backend.app.api.routes.liveshell_jobs import (
    api_router as liveshell_jobs_api_router,
    page_router as liveshell_jobs_page_router,
)
from backend.app.api.routes.membership_admin import router as membership_admin_router
from backend.app.api.routes.model_provider_connections import (
    router as model_provider_connections_router,
)
from backend.app.api.routes.mfa import router as mfa_router
from backend.app.api.routes.mcp_bridge import router as mcp_bridge_router
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
from backend.app.api.routes.seldrune_gpt import router as seldrune_gpt_router
from backend.app.api.routes.sense import router as sense_router
from backend.app.api.routes.status import router as status_router
from backend.app.api.routes.sti import router as sti_router
from backend.app.api.routes.tools import router as tools_router
from backend.app.api.routes.webhooks import router as webhooks_router
from backend.app.core.config import settings
from backend.app.services.external_actions import register_default_external_actions

WEB_ROOT = Path(__file__).resolve().parent / "web"


def create_app() -> FastAPI:
    register_default_external_actions()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
    )
    app.include_router(console_router)
    app.include_router(mail_page_router)
    app.include_router(liveshell_mobile_page_router)
    app.include_router(live_profile_authorizations_page_router)
    app.include_router(liveshell_jobs_page_router)
    app.mount("/console-assets", StaticFiles(directory=WEB_ROOT), name="console-assets")
    app.mount("/mail-assets", StaticFiles(directory=WEB_ROOT), name="mail-assets")
    app.mount("/web", StaticFiles(directory=WEB_ROOT), name="web-assets")
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
        model_provider_connections_router,
        knowledge_router,
        life_router,
        mail_router,
        mail_oauth_router,
        liveshift_face_router,
        live_profile_authorizations_router,
        live_profile_authorizer_internal_router,
        liveshell_mobile_api_router,
        liveshell_jobs_api_router,
        secret_references_router,
        security_events_router,
        seldrune_gpt_router,
        research_router,
        webhooks_router,
        audit_router,
        billing_router,
        development_mission_router,
    ):
        app.include_router(item, prefix=settings.api_v1_prefix)
    app.include_router(mcp_bridge_router)
    return app


app = create_app()

