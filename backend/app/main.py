from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes.agent_tasks import router as agent_tasks_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.console import router as console_router
from backend.app.api.routes.executive_brief import router as executive_brief_router
from backend.app.api.routes.knowledge import router as knowledge_router
from backend.app.api.routes.orchestrations import router as orchestrations_router
from backend.app.api.routes.organization_kernel import router as organization_kernel_router
from backend.app.api.routes.organizations import router as organizations_router
from backend.app.api.routes.owner_attention import router as owner_attention_router
from backend.app.api.routes.owner_commands import router as owner_commands_router
from backend.app.api.routes.owner_push import router as owner_push_router
from backend.app.api.routes.research import router as research_router
from backend.app.api.routes.runtime import router as runtime_router
from backend.app.api.routes.sense import router as sense_router
from backend.app.api.routes.status import router as status_router
from backend.app.api.routes.tools import router as tools_router
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
        auth_router,
        organizations_router,
        organization_kernel_router,
        executive_brief_router,
        owner_attention_router,
        owner_push_router,
        agent_tasks_router,
        orchestrations_router,
        sense_router,
        owner_commands_router,
        runtime_router,
        tools_router,
        knowledge_router,
        research_router,
    ):
        app.include_router(item, prefix=settings.api_v1_prefix)
    return app


app = create_app()
