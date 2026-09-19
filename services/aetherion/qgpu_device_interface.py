"""Hardware-emulation boundary for future Aetherion device backends."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .qgpu_model import EvidenceLevel


class DeviceMode(StrEnum):
    CLASSICAL_SIMULATOR = "classical_simulator"
    FPGA_EMULATION = "fpga_emulation"
    PHYSICAL_QGPU = "physical_qgpu"


@dataclass(frozen=True)
class DeviceCapability:
    mode: DeviceMode
    executable: bool
    verified: bool
    evidence: EvidenceLevel


def current_capabilities() -> tuple[DeviceCapability, ...]:
    return (
        DeviceCapability(DeviceMode.CLASSICAL_SIMULATOR, True, True, EvidenceLevel.EXPERIMENTAL),
        DeviceCapability(DeviceMode.FPGA_EMULATION, False, False, EvidenceLevel.HYPOTHETICAL),
        DeviceCapability(DeviceMode.PHYSICAL_QGPU, False, False, EvidenceLevel.HYPOTHETICAL),
    )
