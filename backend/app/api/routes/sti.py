from pathlib import Path

from fastapi import APIRouter

from services.supreme.run_state import RunState
from services.supreme.run_store import RunStore
from services.live_media.hardware_profiles import default_live_media_accelerator
from services.live_media.readiness import check_readiness

router = APIRouter(prefix="/sti", tags=["seldrune-sti"])


def _store() -> RunStore:
    path = Path("data") / "supreme-runs.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return RunStore(path)


@router.get("/telemetry")
def sti_telemetry() -> dict[str, object]:
    """Measured Seldrune STI execution telemetry for the Owner Console."""
    store = _store()
    counts = store.state_counts()
    recent = store.recent()
    forge = tuple(item for item in recent if item.run_id.startswith("forge:"))
    live_media = check_readiness()
    accelerator = default_live_media_accelerator()
    return {
        "system": "Seldrune STI — Aethelion Intelligence Foundry",
        "source": "durable-run-store",
        "counts": {state.value: counts[state] for state in RunState},
        "liveshift": {
            "webrtc_runtime": live_media.webrtc.available,
            "cuda_runtime": live_media.gpu.cuda_available,
            "onnx_runtime": live_media.gpu.onnx_available,
            "tensorrt_runtime": live_media.gpu.tensorrt_available,
            "runtime_ready": live_media.production_ready,
            "face_model_loaded": False,
            "first_frame_transformed": False,
            "live_stream_returned": False,
            "virtual_camera_connected": False,
            "accelerator_profile": accelerator.key,
            "accelerator_name": accelerator.display_name,
            "preferred_vram_gb": accelerator.preferred_vram_gb,
            "note": "Runtime detection only; GPU hardware presence is not asserted by this API.",
        },
        "forge": {
            "queued": sum(item.state == RunState.QUEUED for item in forge),
            "running": sum(item.state == RunState.RUNNING for item in forge),
            "verified": sum(item.state == RunState.VERIFIED for item in forge),
            "failed": sum(item.state == RunState.FAILED for item in forge),
            "recent_count": len(forge),
        },
        "recent": [
            {
                "run_id": item.run_id,
                "task_id": item.task_id,
                "state": item.state.value,
                "attempts": item.attempts,
                "evidence_count": len(item.evidence),
                "error": item.error,
            }
            for item in recent
        ],
    }
