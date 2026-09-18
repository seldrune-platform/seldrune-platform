"""Fail-fast verification for a Seldrune RTX PRO 6000 worker."""
from __future__ import annotations

import subprocess

from services.live_media.capacity import estimate_session_capacity
from services.live_media.hardware_policy import DetectedHardware, admit_hardware
from services.live_media.hardware_profiles import default_live_media_accelerator


def _gpu() -> tuple[str, int]:
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    ).strip().splitlines()[0]
    name, memory_mib = [part.strip() for part in raw.rsplit(",", 1)]
    return name, int(memory_mib)


def main() -> None:
    name, memory_mib = _gpu()
    vram_gb = memory_mib / 1024
    profile = default_live_media_accelerator()
    detected = DetectedHardware(
        device_name=name,
        vram_gb=vram_gb,
        cuda_available=True,
        hardware_video_codec=True,
    )
    admission = admit_hardware(detected, profile)
    print(f"GPU: {name}")
    print(f"VRAM: {vram_gb:.2f} GiB")
    print(f"Profile: {profile.key}")
    print(f"Admission: {admission}")
    print(f"Planning session capacity: {estimate_session_capacity(vram_gb)}")
    if not admission.admitted:
        raise SystemExit("RTX PRO 6000 worker admission failed")
    print("SELD RUNE GPU WORKER: READY")


if __name__ == "__main__":
    main()
