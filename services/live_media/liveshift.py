"""Product identity for Seldrune's authorized live-media subsystem."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveShiftCapability:
    key: str
    name: str
    description: str


PRODUCT_NAME = "Seldrune LiveShift"

CAPABILITIES = (
    LiveShiftCapability(
        "face-studio",
        "Face Studio",
        "Authorized real-time face transformation.",
    ),
    LiveShiftCapability(
        "voice-studio",
        "Voice Studio",
        "Authorized real-time voice transformation.",
    ),
    LiveShiftCapability(
        "live-call",
        "Live Call",
        "Low-latency camera and microphone processing for supported call clients.",
    ),
    LiveShiftCapability(
        "identity-profiles",
        "Identity Profiles",
        "Consent-gated identity profile management.",
    ),
    LiveShiftCapability(
        "performance",
        "Performance",
        "GPU, frame-rate, latency, and stream-health telemetry.",
    ),
)
