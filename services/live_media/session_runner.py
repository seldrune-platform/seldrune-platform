"""One-session media loop independent of a specific WebRTC library."""
import asyncio

from .pipeline import LivePipeline
from .transport import MediaTransport


async def run_video(transport: MediaTransport, pipeline: LivePipeline) -> None:
    while True:
        frame = await transport.recv_video()
        await transport.send_video(await pipeline.video_frame(frame))


async def run_audio(transport: MediaTransport, pipeline: LivePipeline) -> None:
    while True:
        frame = await transport.recv_audio()
        await transport.send_audio(await pipeline.audio_frame(frame))


async def run_session(
    transport: MediaTransport, pipeline: LivePipeline
) -> None:
    try:
        await asyncio.gather(
            run_video(transport, pipeline),
            run_audio(transport, pipeline),
        )
    finally:
        await transport.close()
