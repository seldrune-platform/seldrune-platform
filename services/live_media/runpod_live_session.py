"""Session-scoped bridge from LivePipeline to one authenticated RunPod client."""

from __future__ import annotations

import re
import ssl
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .gpu_scheduler import GPUWorker
from .pipeline import LivePipeline
from .processors import MediaFrame
from .remote_processors import RemoteAudioProcessor, RemoteVideoProcessor
from .runpod_live_transport import RunPodLiveWorkerClient
from .worker_pool import WorkerPool


ClientFactory = Callable[..., Awaitable[RunPodLiveWorkerClient]]


def _validate_session_fields(
    session_id: str,
    face_profile_id: str,
    voice_profile_id: str,
    region: str,
    max_inflight: int,
) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise ValueError("invalid live session id")
    if not face_profile_id or not voice_profile_id:
        raise ValueError("both authorized media profiles are required")
    if not region:
        raise ValueError("RunPod worker region is required")
    if not 1 <= max_inflight <= 2:
        raise ValueError("live sessions support one or two in-flight media requests")


@dataclass
class RunPodLiveSession:
    """Bind one authorized media session to one long-lived GPU worker connection.

    The caller must provide a signed ticket issued after profile authorization,
    consent, and synthetic-media disclosure checks. The RunPod handshake validates
    the ticket before this session becomes available to the media gateway.
    """

    session_id: str
    face_profile_id: str
    voice_profile_id: str
    region: str
    client: RunPodLiveWorkerClient
    max_inflight: int = 2
    pipeline: LivePipeline = field(init=False)
    _closed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._validate_bindings()
        worker = GPUWorker(
            worker_id=f"runpod-live:{self.session_id}",
            region=self.region,
            capacity=self.max_inflight,
        )
        pool = WorkerPool(workers=[worker], call_worker=self.client)
        self.pipeline = LivePipeline(
            video=RemoteVideoProcessor(
                pool=pool,
                session_id=self.session_id,
                profile_id=self.face_profile_id,
                region=self.region,
            ),
            audio=RemoteAudioProcessor(
                pool=pool,
                session_id=self.session_id,
                profile_id=self.voice_profile_id,
                region=self.region,
            ),
            face_profile_id=self.face_profile_id,
            voice_profile_id=self.voice_profile_id,
        )

    def _validate_bindings(self) -> None:
        _validate_session_fields(
            self.session_id,
            self.face_profile_id,
            self.voice_profile_id,
            self.region,
            self.max_inflight,
        )

    @classmethod
    async def connect(
        cls,
        *,
        host: str,
        port: int,
        service_token: str,
        ticket: str,
        session_id: str,
        face_profile_id: str,
        voice_profile_id: str,
        region: str,
        ssl_context: ssl.SSLContext,
        server_hostname: str,
        max_inflight: int = 2,
        client_factory: ClientFactory | None = None,
    ) -> RunPodLiveSession:
        if not host or not 1 <= port <= 65535:
            raise ValueError("valid RunPod worker host and port are required")
        if not service_token or not ticket or not server_hostname:
            raise ValueError("authenticated worker connection details are required")
        if (
            ssl_context is None
            or ssl_context.verify_mode == ssl.CERT_NONE
            or not ssl_context.check_hostname
        ):
            raise ValueError("RunPod live media requires verified TLS")
        _validate_session_fields(
            session_id,
            face_profile_id,
            voice_profile_id,
            region,
            max_inflight,
        )
        connector = client_factory or RunPodLiveWorkerClient.connect
        client = await connector(
            host,
            port,
            service_token=service_token,
            ticket=ticket,
            session_id=session_id,
            ssl_context=ssl_context,
            server_hostname=server_hostname,
            max_inflight=max_inflight,
        )
        try:
            return cls(
                session_id=session_id,
                face_profile_id=face_profile_id,
                voice_profile_id=voice_profile_id,
                region=region,
                client=client,
                max_inflight=max_inflight,
            )
        except Exception:
            await client.close()
            raise

    async def video_frame(self, frame: MediaFrame) -> MediaFrame:
        self._ensure_open()
        return await self.pipeline.video_frame(frame)

    async def audio_frame(self, frame: MediaFrame) -> MediaFrame:
        self._ensure_open()
        return await self.pipeline.audio_frame(frame)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self.client.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("live session is closed")
