"""Graphics-oriented kernels for Aetherion universal compute research."""

from __future__ import annotations

from dataclasses import dataclass

from .qgpu_model import EvidenceLevel


@dataclass(frozen=True)
class GraphicsReceipt:
    pixels: tuple[float, ...]
    operations: int
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL
    physical_graphics_hardware_verified: bool = False


def shade_lambert(
    intensities: tuple[float, ...],
    normal_dot_light: tuple[float, ...],
) -> GraphicsReceipt:
    if len(intensities) != len(normal_dot_light):
        raise ValueError("graphics inputs must have equal length")
    pixels = tuple(
        intensity * max(0.0, dot)
        for intensity, dot in zip(intensities, normal_dot_light, strict=True)
    )
    return GraphicsReceipt(pixels, len(pixels) * 2)
