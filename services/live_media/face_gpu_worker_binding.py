"""Bind an admitted GPU execution manifest to verifiable worker evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_receipt import GpuTrainingReceipt


@dataclass(frozen=True)
class GpuWorkerIdentity:
    worker_id: str
    accelerator: str
    cuda_available: bool

    def validate(self) -> None:
        if not self.worker_id or not self.accelerator:
            raise ValueError("worker identity is required")
        if not self.cuda_available:
            raise ValueError("Face GPU training requires CUDA")


def verify_execution_receipt(
    execution: GpuTrainingExecution,
    receipt: GpuTrainingReceipt,
    worker: GpuWorkerIdentity,
) -> None:
    """Reject evidence that cannot be bound to the admitted execution."""
    execution.validate()
    receipt.validate()
    worker.validate()

    if receipt.job_id != execution.job_id:
        raise ValueError("receipt job does not match execution")
    if receipt.execution_digest != execution.digest():
        raise ValueError("receipt execution digest does not match execution")
    if receipt.model_version != execution.model_version:
        raise ValueError("receipt model version does not match execution")
    if receipt.accelerator != execution.accelerator:
        raise ValueError("receipt accelerator does not match execution")
    if worker.accelerator != execution.accelerator:
        raise ValueError("worker accelerator does not match execution")
    if receipt.dataset_manifest_sha256 != execution.dataset_manifest_sha256:
        raise ValueError("receipt dataset manifest does not match execution")
    if receipt.final_step > execution.max_steps:
        raise ValueError("receipt exceeds admitted training step budget")


@dataclass(frozen=True)
class GpuWorkerRunEnvelope:
    worker: GpuWorkerIdentity
    execution: GpuTrainingExecution
    admitted_at: datetime

    def validate(self) -> None:
        self.worker.validate()
        self.execution.validate()
        if self.worker.accelerator != self.execution.accelerator:
            raise ValueError("worker cannot admit this accelerator profile")
