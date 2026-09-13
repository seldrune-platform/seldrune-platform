from fastapi import APIRouter

router = APIRouter(tags=["status"])


@router.get("/status")
def service_status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "seldrune-platform",
        "version": "0.1.0",
    }
