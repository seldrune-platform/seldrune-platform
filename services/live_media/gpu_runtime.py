"""Cloud GPU runtime contract and health/capacity model."""
from dataclasses import dataclass
from enum import Enum

class RuntimeKind(str,Enum):
    CUDA="cuda"; TENSORRT="tensorrt"; ONNX_CUDA="onnx-cuda"

@dataclass(frozen=True)
class GPUCapabilities:
    device_name:str
    total_vram_mb:int
    runtime:RuntimeKind
    nvenc:bool=True
    nvdec:bool=True

@dataclass
class GPUHealth:
    gpu_utilization:float=0.0
    vram_used_mb:int=0
    temperature_c:float=0.0
    healthy:bool=True

def can_accept(cap:GPUCapabilities, health:GPUHealth, reserve_mb:int=2048)->bool:
    return health.healthy and health.gpu_utilization<0.92 and (cap.total_vram_mb-health.vram_used_mb)>=reserve_mb
