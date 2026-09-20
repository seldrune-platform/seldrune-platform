"""One-session media loop independent of a specific WebRTC library."""

import asyncio
from time import monotonic
from typing import Protocol

from .pipeline import LivePipeline
from .transport import MediaTransport


class ReturnedFrameObserver(Protocol):
    def record_returned_frame(self, latency_ms: float) -> None: ...


class ReturnedAudioObserver(Protocol):
    def record_returned_audio_timestamp(self, timestamp_ms: int) -> None: ...


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


async def run_audio(
    transport: MediaTransport,
    pipeline: LivePipeline,
    observer: ReturnedAudioObserver | None = None,
) -> None:
    while True:
        frame = await transport.recv_audio()
        output = await pipeline.audio_frame(frame)
        await transport.send_audio(output)
        if observer is not None:
            observer.record_returned_audio_timestamp(output.timestamp_ms)


async def run_session(
    transport: MediaTransport,
    pipeline: LivePipeline,
    *,
    video_observer: ReturnedFrameObserver | None = None,
    audio_observer: ReturnedAudioObserver | None = None,
) -> None:
    try:
        await asyncio.gather(
            run_video(transport, pipeline, video_observer),
            run_audio(transport, pipeline, audio_observer),
        )
    finally:
        await transport.close()
