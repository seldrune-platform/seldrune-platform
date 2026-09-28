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

# Deployment targets, not measured capacity guarantees.
RTX_4090_ADA = AcceleratorProfile(
    key="rtx-4090",
    display_name="NVIDIA GeForce RTX 4090",
    min_vram_gb=24,
    preferred_vram_gb=24,
    cuda_required=True,
    hardware_video_codec_preferred=True,
)

RTX_5090_BLACKWELL = AcceleratorProfile(
    key="rtx-5090",
    display_name="NVIDIA GeForce RTX 5090",
    min_vram_gb=32,
    preferred_vram_gb=32,
    cuda_required=True,
    hardware_video_codec_preferred=True,
)

LIVE_MEDIA_TARGET_PROFILES = (
    RTX_4090_ADA,
    RTX_5090_BLACKWELL,
    RTX_PRO_6000_BLACKWELL,
)


def live_media_accelerator_profile(key: str) -> AcceleratorProfile:
    """Resolve an explicitly selected target profile."""
    for profile in LIVE_MEDIA_TARGET_PROFILES:
        if profile.key == key:
            return profile
    raise ValueError(f"unsupported LiveShell accelerator profile: {key}")


