"""Deployment readiness report for the live media data plane."""
from dataclasses import dataclass

from .gpu_backend_runtime import GPUBackendStatus, detect_gpu_backends
from .webrtc_runtime import WebRTCRuntimeStatus, detect_webrtc_runtime


@dataclass(frozen=True)
class LiveMediaReadiness:
    webrtc: WebRTCRuntimeStatus
    gpu: GPUBackendStatus

    @property
    def production_ready(self) -> bool:
        return self.webrtc.available and (
            self.gpu.cuda_available
            or self.gpu.onnx_available
            or self.gpu.tensorrt_available
        )


def check_readiness() -> LiveMediaReadiness:
    return LiveMediaReadiness(
        webrtc=detect_webrtc_runtime(),
        gpu=detect_gpu_backends(),
    )
