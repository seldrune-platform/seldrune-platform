"""Runtime detection for optional cloud GPU inference providers."""
from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True)
class GPUBackendStatus:
    cuda_available: bool
    onnx_available: bool
    tensorrt_available: bool


def detect_gpu_backends() -> GPUBackendStatus:
    return GPUBackendStatus(
        cuda_available=find_spec("torch") is not None,
        onnx_available=find_spec("onnxruntime") is not None,
        tensorrt_available=find_spec("tensorrt") is not None,
    )
