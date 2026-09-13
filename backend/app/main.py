from fastapi import FastAPI

from backend.app.api.routes.status import router as status_router
from backend.app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
    )
    app.include_router(status_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
