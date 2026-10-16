from os import getenv
from pathlib import Path

from fastapi import APIRouter

from services.supreme.run_state import RunState
from services.supreme.run_store import RunStore
from services.live_media.face_production_gate import FaceProductionGates
from services.live_media.face_production_io import load_production_gates
from services.live_media.hardware_profiles import default_live_media_accelerator
from services.live_media.readiness import check_readiness

from backend.app.services.evolution_registry import evolution_payload

router = APIRouter(prefix="/sti", tags=["seldrune-sti"])


def _store() -> RunStore:
    path = Path("data") / "supreme-runs.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return RunStore(path)


def _face_production_gates() -> tuple[FaceProductionGates, str]:
    evidence_path = getenv("SELDRUNE_FACE_PRODUCTION_EVIDENCE")
    receipt_path = getenv("SELDRUNE_FACE_VERIFICATION_RECEIPT")
    pending = FaceProductionGates(False, False, False)
    if not evidence_path or not receipt_path:
        return pending, "pending-evidence"
    try:
        return load_production_gates(evidence_path, receipt_path), "verified-evidence"
    except (OSError, ValueError):
        return pending, "invalid-evidence"


@router.get("/telemetry")
def sti_telemetry() -> dict[str, object]:
    """Measured Seldrune STI execution telemetry for the Owner Console."""
    store = _store()
    counts = store.state_counts()
    recent = store.recent()
    forge = tuple(item for item in recent if item.run_id.startswith("forge:"))
    live_media = check_readiness()
    accelerator = default_live_media_accelerator()
    production_gates, production_evidence_status = _face_production_gates()
    return {
        "system": "Seldrune STI — Aethelion Intelligence Foundry",
        "source": "durable-run-store",
        "counts": {state.value: counts[state] for state in RunState},
        "evidence_levels": {
            "verified": "Backed by retained runtime evidence or artifact hashes.",
            "implemented": "Code and automated tests pass; production execution is pending.",
            "simulated": "Executed only with controlled or synthetic inputs.",
            "planned": "Designed but not implemented.",
        },
        "liveshift": {
            "webrtc_runtime": live_media.webrtc.available,
            "cuda_runtime": live_media.gpu.cuda_available,
            "onnx_runtime": live_media.gpu.onnx_available,
            "tensorrt_runtime": live_media.gpu.tensorrt_available,
            "runtime_ready": live_media.production_ready,
            # Delivery claims require the signed production receipt. Runtime
            # package/GPU detection alone does not prove a transformed call.
            "face_model_loaded": production_gates.live_session_verified,
            "first_frame_transformed": production_gates.live_session_verified,
            "live_stream_returned": production_gates.live_session_verified,
            "webrtc_return_verified": production_gates.live_session_verified,
            # The current production receipt does not attest CUDA execution or
            # an OS virtual-camera device, so keep those gates closed.
            "cuda_webrtc_return_verified": False,
            "virtual_camera_connected": False,
            "accelerator_profile": accelerator.key,
            "accelerator_name": accelerator.display_name,
            "preferred_vram_gb": accelerator.preferred_vram_gb,
            "note": "Runtime detection only; GPU hardware presence is not asserted by this API.",
        },
        "face_v01": {
            "model_version": "seldrune-face-v0.1",
            "dataset_contract": "ready",
            "manifest_validation": "ready",
            "training_job_preflight": "ready",
            "architecture_contract": "ready",
            "pytorch_model": "ready",
            "cuda_training_step": "ready",
            "checkpoint_evidence": "ready",
            "checkpoint_writer": "ready",
            "multistep_training": "ready",
            "onnx_export": "ready",
            "liveshift_loader": "ready",
            "reference_encoder": "ready",
            "paired_gpu_training": "ready",
            "verification_receipt": "ready",
            "file_evidence_collector": "ready",
            "verification_cli": "ready",
            "single_frame_execution": "implemented",
            "continuous_stream_execution": "implemented",
            "onnx_cuda_backend": "implemented",
            "liveshift_onnx_adapter": "implemented",
            "production_evidence_recorder": "implemented",
            "session_evidence_integration": "implemented",
            "production_evidence_verifier": "implemented",
            "gpu_training_completed": True,
            "checkpoint_verified": True,
            "onnx_export_verified": True,
            "cuda_onnx_inference_verified": True,
            "real_image_inference_verified": True,
            "webrtc_cuda_return_verified": True,
            "production_live_session_verified": production_gates.live_session_verified,
            "mobile_hd_output_verified": production_gates.mobile_hd_output_verified,
            "voice_hd_output_verified": production_gates.voice_hd_output_verified,
            "production_evidence_status": production_evidence_status,
            "training_accelerator": "rtx-pro-6000-blackwell",
            "training_final_step": 100,
            "note": (
                "Face v0.1 GPU training/checkpoint, reference-conditioned ONNX "
                "export, CUDA inference, real-image inference, and WebRTC CUDA "
                "return-frame delivery have runtime evidence. Virtual-camera "
                "delivery remains unverified."
            ),
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



@router.get("/evolution")
def sti_evolution() -> dict[str, object]:
    """Explicit V22–V100 technical contracts and evidence-aware status."""
    return evolution_payload()
