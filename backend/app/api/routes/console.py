from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["owner-console"])
WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


@router.get("/console", include_in_schema=False)
def owner_console() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")
