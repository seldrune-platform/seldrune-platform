"""End-to-end authorized live-media session coordinator."""
import asyncio
from dataclasses import dataclass

from .pipeline import LivePipeline
from .stream_lifecycle import StreamLifecycle
from .transport import MediaTransport


@dataclass
class LiveSessionEngine:
    transport: MediaTransport
    pipeline: LivePipeline
    lifecycle: StreamLifecycle

    async def _video_loop(self) -> None:
        while True:
            frame = await self.transport.recv_video()
            output = await self.pipeline.video_frame(frame)
            await self.transport.send_video(output)

    async def _audio_loop(self) -> None:
        while True:
            frame = await self.transport.recv_audio()
            output = await self.pipeline.audio_frame(frame)
            await self.transport.send_audio(output)

    async def run(self) -> None:
        self.lifecycle.start()
        tasks: list[asyncio.Task] = []
        try:
            self.lifecycle.activate()
            tasks = [
                asyncio.create_task(self._video_loop()),
                asyncio.create_task(self._audio_loop()),
            ]
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.lifecycle.fail(exc)
            raise
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await self.transport.close()
            if self.lifecycle.error is None:
                self.lifecycle.close()
