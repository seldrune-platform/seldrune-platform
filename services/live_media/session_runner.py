"""One-session media loop independent of a specific WebRTC library."""

import asyncio
from time import monotonic
from typing import Protocol

from .pipeline import LivePipeline
from .transport import MediaTransport


class ReturnedFrameObserver(Protocol):
    def record_returned_frame(self, latency_ms: float) -> None: ...


async def run_video(
    transport: MediaTransport,
    pipeline: LivePipeline,
    observer: ReturnedFrameObserver | None = None,
) -> None:
    while True:
        frame = await transport.recv_video()
        started = monotonic()
        output = await pipeline.video_frame(frame)
        await transport.send_video(output)
        if observer is not None:
            observer.record_returned_frame((monotonic() - started) * 1000)


async def run_audio(transport: MediaTransport, pipeline: LivePipeline) -> None:
    while True:
        frame = await transport.recv_audio()
        await transport.send_audio(await pipeline.audio_frame(frame))


async def run_session(
    transport: MediaTransport,
    pipeline: LivePipeline,
    *,
    video_observer: ReturnedFrameObserver | None = None,
) -> None:
    try:
        await asyncio.gather(
            run_video(transport, pipeline, video_observer),
            run_audio(transport, pipeline),
        )
    finally:
        await transport.close()
