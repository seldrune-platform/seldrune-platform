"""Hardware admission policy for Seldrune Live GPU workers."""
from dataclasses import dataclass

from .hardware_profiles import AcceleratorProfile


@dataclass(frozen=True)
class DetectedHardware:
    name: str
    vram_gb: int
    cuda_available: bool
    hardware_video_codec: bool


@dataclass(frozen=True)
class HardwareAdmission:
    accepted: bool
    reasons: tuple[str, ...]


def admit_hardware(
    hardware: DetectedHardware,
    profile: AcceleratorProfile,
) -> HardwareAdmission:
    reasons: list[str] = []
    if profile.cuda_required and not hardware.cuda_available:
        reasons.append("CUDA runtime unavailable")
    if hardware.vram_gb < profile.min_vram_gb:
        reasons.append("insufficient VRAM")
    if (
        profile.hardware_video_codec_preferred
        and not hardware.hardware_video_codec
    ):
        reasons.append("hardware video codec unavailable")
    return HardwareAdmission(not reasons, tuple(reasons))
