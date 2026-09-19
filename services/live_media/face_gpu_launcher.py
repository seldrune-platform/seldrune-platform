"""Provider-neutral launch contract for Seldrune Face GPU training workers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from services.live_media.face_gpu_execution import GpuTrainingExecution
from services.live_media.face_gpu_worker_binding import GpuWorkerIdentity


@dataclass(frozen=True)
class GpuLaunchRequest:
    execution: GpuTrainingExecution
    worker: GpuWorkerIdentity
    command: tuple[str, ...]
    environment_keys: tuple[str, ...] = ()

    def validate(self) -> None:
        self.execution.validate()
        self.worker.validate()
        if self.worker.accelerator != self.execution.accelerator:
            raise ValueError("worker accelerator does not match execution")
        if not self.command or any(not part for part in self.command):
            raise ValueError("launch command is required")
        if len(set(self.environment_keys)) != len(self.environment_keys):
            raise ValueError("environment keys must be unique")


@dataclass(frozen=True)
class GpuLaunchHandle:
    provider: str
    worker_id: str
    remote_run_id: str

    def validate(self) -> None:
        if not self.provider or not self.worker_id or not self.remote_run_id:
            raise ValueError("provider, worker and remote run identifiers are required")


class GpuWorkerLauncher(Protocol):
    async def launch(self, request: GpuLaunchRequest) -> GpuLaunchHandle:
        """Launch an admitted training execution on a remote GPU worker."""


def build_face_training_launch(
    execution: GpuTrainingExecution,
    worker: GpuWorkerIdentity,
) -> GpuLaunchRequest:
    request = GpuLaunchRequest(
        execution=execution,
        worker=worker,
        command=(
            "python",
            "-m",
            "services.live_media.face_gpu_worker",
            "--execution-manifest",
            "execution.json",
        ),
        environment_keys=("SELDRUNE_GPU_WORKER_ID",),
    )
    request.validate()
    return request
