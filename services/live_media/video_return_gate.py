"""Finite LiveShift video-return gate for transformed-frame verification."""

from __future__ import annotations

from dataclasses import dataclass

from .pipeline import LivePipeline
from .transport import MediaTransport


@dataclass(frozen=True)
class VideoReturnEvidence:
    frames_received: int
    frames_returned: int
    transformed_frames: int

    @property
    def verified(self) -> bool:
        return (
            self.frames_received > 0
            and self.frames_received == self.frames_returned
            and self.transformed_frames > 0
        )


async def run_video_return_gate(
    transport: MediaTransport,
    pipeline: LivePipeline,
    *,
    frame_limit: int = 1,
) -> VideoReturnEvidence:
    """Process a finite number of video frames and verify outbound delivery.

    This deliberately avoids asserting WebRTC: a concrete WebRTC adapter must
    supply the transport before its runtime evidence can be called WebRTC.
    """
    if frame_limit < 1:
        raise ValueError("frame_limit must be positive")

    received = returned = transformed = 0
    for _ in range(frame_limit):
        source = await transport.recv_video()
        received += 1
        output = await pipeline.video_frame(source)
        await transport.send_video(output)
        returned += 1
        if output.payload != source.payload:
            transformed += 1

    return VideoReturnEvidence(received, returned, transformed)
