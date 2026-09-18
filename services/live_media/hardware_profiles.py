"""First-class accelerator profiles for the Seldrune media plane."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AcceleratorProfile:
    key: str
    display_name: str
    min_vram_gb: int
    preferred_vram_gb: int
    cuda_required: bool
    hardware_video_codec_preferred: bool


RTX_PRO_6000_BLACKWELL = AcceleratorProfile(
    key="rtx-pro-6000-blackwell",
    display_name="NVIDIA RTX PRO 6000 Blackwell",
    min_vram_gb=90,
    preferred_vram_gb=96,
    cuda_required=True,
    hardware_video_codec_preferred=True,
)


def default_live_media_accelerator() -> AcceleratorProfile:
    return RTX_PRO_6000_BLACKWELL
