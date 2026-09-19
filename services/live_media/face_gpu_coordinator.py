"""End-to-end coordinator for admitted Seldrune Face GPU training."""
from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_receipt import GpuExecutionState, GpuTrainingReceipt
from services.live_media.face_paired_batches import build_paired_batches
from services.live_media.face_paired_runtime import build_paired_gpu_runtime
from services.live_media.face_gpu_training_bridge import execute_admitted_paired_training
from services.live_media.face_tensor_batches import FaceTrainingSample

RTX_PRO_6000_PROFILE = "rtx-pro-6000-blackwell"

@dataclass(frozen=True)
class CoordinatedGpuTraining:
    receipt: GpuTrainingReceipt
    last_loss: float

def coordinate_gpu_training(execution: GpuTrainingExecution, samples: Iterable[FaceTrainingSample], *, batch_size: int) -> CoordinatedGpuTraining:
    """Run the Seldrune-owned reference-conditioned paired path on admitted CUDA work."""
    execution.validate()
    if execution.accelerator != RTX_PRO_6000_PROFILE:
        raise ValueError("paired Face v0.1 training requires the RTX PRO 6000 profile")
    started_at = datetime.now(UTC)
    runtime = build_paired_gpu_runtime(execution)
    batches = build_paired_batches(samples, batch_size=batch_size)
    result = execute_admitted_paired_training(
        execution, runtime.model, runtime.optimizer, batches, device=runtime.device
    )
    completed_at = datetime.now(UTC)
    receipt = GpuTrainingReceipt(
        job_id=execution.job_id, execution_digest=execution.digest(),
        model_version=execution.model_version, accelerator=execution.accelerator,
        dataset_manifest_sha256=execution.dataset_manifest_sha256,
        started_at=started_at, completed_at=completed_at,
        final_step=result.completed_steps,
        checkpoint_sha256=tuple(item.sha256 for item in result.checkpoints),
        state=GpuExecutionState.SUCCEEDED,
    )
    receipt.validate()
    return CoordinatedGpuTraining(receipt=receipt, last_loss=result.last_loss)
