"""Concrete-runtime seam for WebRTC implementations.

The core package deliberately avoids importing a WebRTC dependency at module
load time. Production deployments can install a supported adapter while tests
and the control plane remain lightweight.
"""
from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True)
class WebRTCRuntimeStatus:
    provider: str
    available: bool
    detail: str


def detect_webrtc_runtime() -> WebRTCRuntimeStatus:
    if find_spec("aiortc") is not None:
        return WebRTCRuntimeStatus(
            provider="aiortc",
            available=True,
            detail="Python WebRTC runtime available",
        )
    return WebRTCRuntimeStatus(
        provider="none",
        available=False,
        detail="Install a supported WebRTC adapter in the media deployment",
    )
