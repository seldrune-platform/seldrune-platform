from services.live_media.hardware_profiles import (
    RTX_4090_ADA,
    RTX_5090_BLACKWELL,
    live_media_accelerator_profile,
)


def test_4090_is_available_as_the_baseline_live_media_target():
    assert live_media_accelerator_profile("rtx-4090") == RTX_4090_ADA
    assert RTX_4090_ADA.preferred_vram_gb == 24


def test_5090_is_a_higher_headroom_live_media_target():
    assert live_media_accelerator_profile("rtx-5090") == RTX_5090_BLACKWELL
    assert RTX_5090_BLACKWELL.preferred_vram_gb == 32
    assert RTX_5090_BLACKWELL.preferred_vram_gb > RTX_4090_ADA.preferred_vram_gb

