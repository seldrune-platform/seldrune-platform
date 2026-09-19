"""Combined LiveShift A/V synchronization proof helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .pipeline import LivePipeline


@dataclass(frozen=True)
class AVReturnEvidence:
    video_returned: bool
    audio_returned: bool
    drift_ms: int
    max_drift_ms: int
    correction: str

    @property
    def verified(self) -> bool:
        return (
            self.video_returned
            and self.audio_returned
            and abs(self.drift_ms) <= self.max_drift_ms
        )

    def as_receipt(self) -> dict[str, object]:
        receipt = asdict(self)
        receipt["state"] = "succeeded" if self.verified else "failed"
        receipt["combined_av_return_verified"] = self.verified
        return receipt


def capture_av_return_evidence(
    pipeline: LivePipeline,
    *,
    video_returned: bool,
    audio_returned: bool,
) -> AVReturnEvidence:
    """Capture measured A/V drift from the shared LivePipeline sync state."""
    if pipeline.sync is None:
        raise RuntimeError("LivePipeline AVSyncState is required")
    return AVReturnEvidence(
        video_returned=video_returned,
        audio_returned=audio_returned,
        drift_ms=pipeline.sync.drift_ms,
        max_drift_ms=pipeline.sync.max_drift_ms,
        correction=pipeline.sync.correction(),
    )
