from services.live_media.capacity import DEFAULT_RTX_PRO_6000_CAPACITY
from services.live_media.hardware_policy import DetectedHardware, admit_hardware
from services.live_media.hardware_profiles import (
    RTX_PRO_6000_BLACKWELL,
    default_live_media_accelerator,
)


def test_rtx_pro_6000_is_default_accelerator():
    assert default_live_media_accelerator() == RTX_PRO_6000_BLACKWELL
    assert RTX_PRO_6000_BLACKWELL.preferred_vram_gb == 96


def test_preferred_worker_is_admitted():
    hardware = DetectedHardware(
        "RTX PRO 6000 Blackwell",
        96,
        True,
        True,
    )
    assert admit_hardware(hardware, RTX_PRO_6000_BLACKWELL).accepted


def test_underprovisioned_worker_is_rejected():
    hardware = DetectedHardware("small-gpu", 24, True, True)
    admission = admit_hardware(hardware, RTX_PRO_6000_BLACKWELL)
    assert not admission.accepted
    assert "insufficient VRAM" in admission.reasons


def test_capacity_keeps_vram_reserve():
    capacity = DEFAULT_RTX_PRO_6000_CAPACITY.max_sessions(96)
    assert capacity == 6
