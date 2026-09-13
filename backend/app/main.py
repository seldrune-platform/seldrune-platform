from fastapi import FastAPI

from backend.app.api.routes.agent_tasks import router as agent_tasks_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.knowledge import router as knowledge_router
from backend.app.api.routes.orchestrations import router as orchestrations_router
from backend.app.api.routes.organizations import router as organizations_router
from backend.app.api.routes.research import router as research_router
from backend.app.api.routes.runtime import router as runtime_router
from backend.app.api.routes.status import router as status_router
from backend.app.api.routes.tools import router as tools_router
from backend.app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
    )
    app.include_router(status_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(organizations_router, prefix=settings.api_v1_prefix)
    app.include_router(agent_tasks_router, prefix=settings.api_v1_prefix)
    app.include_router(orchestrations_router, prefix=settings.api_v1_prefix)
    app.include_router(runtime_router, prefix=settings.api_v1_prefix)
    app.include_router(tools_router, prefix=settings.api_v1_prefix)
    app.include_router(knowledge_router, prefix=settings.api_v1_prefix)
    app.include_router(research_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
