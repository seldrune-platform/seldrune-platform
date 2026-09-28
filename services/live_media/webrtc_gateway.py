"""Authenticated WebRTC signaling gateway for LiveShell.

Profile authorization is supplied by a trusted deployment adapter. There is no
allow-all default, and transformed frames pass through the strict RunPod worker.
"""

from __future__ import annotations

import asyncio
import hmac
import importlib
import json
import math
import os
import re
import ssl
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from time import monotonic, time
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .aiortc_audio_track import attach_audio_track
from .aiortc_video_track import attach_video_track
from .processors import MediaFrame
from .runpod_live_session import RunPodLiveSession
from .runpod_live_transport import (
    MAX_TICKET_TTL_SECONDS,
    SessionTicketClaims,
    issue_session_ticket,
)
from .transport_metadata import DeliveredAudioMetadata, DeliveredVideoMetadata

SUPPORTED_ACCELERATOR_PROFILES = frozenset({
    "rtx-4090", "rtx-pro-4500-se", "rtx-5090", "rtx-pro-6000-blackwell",
})


@dataclass(frozen=True)
class ProfileAuthorization:
    face_profile_authorized: bool
    voice_profile_authorized: bool


ProfileAuthorizer = Callable[..., Awaitable[ProfileAuthorization] | ProfileAuthorization]
WorkerSessionFactory = Callable[..., Awaitable[RunPodLiveSession]]
PeerFactory = Callable[[list["IceServer"]], object]


@dataclass(frozen=True)
class IceServer:
    urls: list[str]
    username: str | None = None
    credential: str | None = None

    def __post_init__(self) -> None:
        allowed = ("stun:", "stuns:", "turn:", "turns:")
        if not self.urls or any(not url.startswith(allowed) for url in self.urls):
            raise ValueError("ICE server URLs must use STUN or TURN")
        if (self.username is None) != (self.credential is None):
            raise ValueError("TURN username and credential must be supplied together")


@dataclass(frozen=True)
class GatewaySettings:
    http_service_token: str
    worker_service_token: str
    ticket_secret: str
    worker_host: str
    worker_port: int
    worker_tls_server_name: str
    worker_region: str
    ice_servers: list[IceServer]
    max_sessions: int = 1
    max_inflight: int = 2
    session_ttl_seconds: int = 3600

    def __post_init__(self) -> None:
        for name, value in (
            ("HTTP service token", self.http_service_token),
            ("RunPod service token", self.worker_service_token),
            ("ticket signing secret", self.ticket_secret),
        ):
            if len(value.encode("utf-8")) < 32:
                raise ValueError(f"{name} must contain at least 32 bytes")
        if not self.worker_host or not self.worker_tls_server_name or not self.worker_region:
            raise ValueError("RunPod worker host, TLS name, and region are required")
        if not 1 <= self.worker_port <= 65535:
            raise ValueError("RunPod worker port is outside the valid range")
        if self.max_sessions < 1 or not 1 <= self.max_inflight <= 2:
            raise ValueError("gateway capacity is outside the supported range")
        if not 60 <= self.session_ttl_seconds <= 24 * 60 * 60:
            raise ValueError("session lifetime must be between one minute and one day")
        if not self.ice_servers:
            raise ValueError("at least one ICE server is required")


class WebRTCOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["offer"]
    sdp: str = Field(min_length=20, max_length=250_000)


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    offer: WebRTCOffer
    face_profile_id: str = Field(
        min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
    voice_profile_id: str = Field(
        min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
    consent_confirmed: StrictBool = False
    synthetic_media_indicator_enabled: StrictBool = False
    video_resolution: Literal["720p", "1080p"] = "1080p"
    target_accelerator_profile: Literal[
        "rtx-4090", "rtx-pro-4500-se", "rtx-5090", "rtx-pro-6000-blackwell"
    ] = "rtx-4090"


class GatewayDescription(BaseModel):
    type: Literal["answer"]
    sdp: str


class GatewaySessionResponse(BaseModel):
    session_id: str
    answer: GatewayDescription
    face_profile_id: str
    voice_profile_id: str
    face_profile_authorized: StrictBool
    voice_profile_authorized: StrictBool
    synthetic_media_indicator_enabled: StrictBool
    runpod_session_connected: StrictBool
    session_ticket_validated: StrictBool
    realism_evidence_required: StrictBool
    actual_accelerator_profile: Literal[
        "rtx-4090", "rtx-pro-4500-se", "rtx-5090", "rtx-pro-6000-blackwell"
    ]
    output_width: int | None = None
    output_height: int | None = None
    audio_sample_rate_hz: int | None = None
    output_fps: float | None = None


@dataclass
class _OutputMetrics:
    """Measurements from frames that have actually reached the peer sender."""

    width: int | None = None
    height: int | None = None
    audio_sample_rate_hz: int | None = None
    _video_times: deque[float] = field(default_factory=lambda: deque(maxlen=30))

    def record_returned_frame(self, _elapsed_ms: float) -> None:
        return

    def record_delivered_video_metadata(self, value: DeliveredVideoMetadata) -> None:
        self.width, self.height = value.width, value.height

    def record_delivered_audio_metadata(self, value: DeliveredAudioMetadata) -> None:
        self.audio_sample_rate_hz = value.sample_rate_hz

    def record_video_delivery(self, at: float) -> None:
        self._video_times.append(at)

    @property
    def measured_fps(self) -> float | None:
        if len(self._video_times) < 5:
            return None
        duration = self._video_times[-1] - self._video_times[0]
        return (len(self._video_times) - 1) / duration if duration > 0 else None


class _MediaClock:
    def __init__(self) -> None:
        self._origin: float | None = None
        self._last: float | None = None

    def timestamp_and_time(self, frame: object) -> tuple[int, float]:
        value = getattr(frame, "time", None)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            pts, base = getattr(frame, "pts", None), getattr(frame, "time_base", None)
            value = float(pts * base) if pts is not None and base is not None else monotonic()
        value = float(value)
        if self._origin is None:
            self._origin = value
        elapsed = max(0.0, value - self._origin)
        if self._last is not None and elapsed <= self._last:
            elapsed = self._last + 0.000001
        self._last = elapsed
        return int(elapsed * 1000), elapsed


class _VideoCodec:
    def __init__(self, metrics: _OutputMetrics) -> None:
        self._clock = _MediaClock()
        self._times: deque[float] = deque(maxlen=15)
        self._metrics = metrics

    async def decode(self, frame: object) -> MediaFrame:
        import numpy as np

        rgb = await asyncio.to_thread(frame.to_ndarray, format="rgb24")
        height, width, channels = rgb.shape
        short_edge, long_edge = sorted((int(width), int(height)))
        if channels != 3 or not (720 <= short_edge <= 1080 and 1280 <= long_edge <= 1920):
            raise ValueError("camera frame is outside the supported 720p/1080p profile")
        timestamp_ms, timestamp_s = self._clock.timestamp_and_time(frame)
        self._times.append(timestamp_s)
        fps = 30.0
        if len(self._times) >= 3:
            duration = self._times[-1] - self._times[0]
            if duration > 0:
                fps = (len(self._times) - 1) / duration
        if not 24.0 <= fps <= 60.0:
            raise ValueError("camera frame rate is outside the supported 24-60 fps range")
        payload = await asyncio.to_thread(lambda: np.ascontiguousarray(rgb).tobytes())
        return MediaFrame(payload, timestamp_ms, int(width), int(height), fps=fps)

    async def encode(self, frame: MediaFrame, original: object) -> object:
        import numpy as np
        from av import VideoFrame

        width = frame.width or int(getattr(original, "width"))
        height = frame.height or int(getattr(original, "height"))
        if len(frame.payload) != width * height * 3:
            raise ValueError("RunPod video result is not packed RGB24 for its dimensions")

        def build() -> object:
            pixels = np.frombuffer(frame.payload, dtype=np.uint8).reshape((height, width, 3))
            returned = VideoFrame.from_ndarray(pixels, format="rgb24")
            returned.pts = getattr(original, "pts", None)
            returned.time_base = getattr(original, "time_base", None)
            return returned

        returned = await asyncio.to_thread(build)
        self._metrics.record_video_delivery(monotonic())
        return returned


class _AudioCodec:
    def __init__(self) -> None:
        self._clock = _MediaClock()
        self._resampler: object | None = None
        self._layout: str | None = None
        self._channels: int | None = None

    def _decode(self, frame: object) -> MediaFrame:
        import numpy as np
        from av import AudioResampler

        layout_obj = getattr(frame, "layout", None)
        layout = getattr(layout_obj, "name", None)
        channels = len(getattr(layout_obj, "channels", ()))
        if layout not in {"mono", "stereo"} or channels not in {1, 2}:
            raise ValueError("LiveShell accepts mono or stereo audio")
        if self._layout is None:
            self._layout, self._channels = layout, channels
            self._resampler = AudioResampler(format="s16", layout=layout, rate=48_000)
        elif layout != self._layout:
            raise ValueError("audio channel layout changed during a live session")
        resampled = self._resampler.resample(frame)
        if not resampled:
            raise ValueError("audio resampler returned no media frame")
        chunks = [np.asarray(part.to_ndarray()).reshape(-1) for part in resampled]
        payload = np.concatenate(chunks).astype("<i2", copy=False).tobytes()
        timestamp_ms, _ = self._clock.timestamp_and_time(frame)
        return MediaFrame(payload, timestamp_ms, sample_rate_hz=48_000, channels=channels)

    async def decode(self, frame: object) -> MediaFrame:
        return await asyncio.to_thread(self._decode, frame)

    def _encode(self, frame: MediaFrame, original: object) -> object:
        from fractions import Fraction
        from av import AudioFrame

        channels = frame.channels or self._channels
        if channels not in {1, 2} or len(frame.payload) % (2 * channels):
            raise ValueError("RunPod audio result is not packed signed-16 PCM")
        layout = "mono" if channels == 1 else "stereo"
        samples = len(frame.payload) // (2 * channels)
        returned = AudioFrame(format="s16", layout=layout, samples=samples)
        returned.sample_rate = frame.sample_rate_hz or 48_000
        returned.planes[0].update(frame.payload)
        returned.pts = getattr(original, "pts", None)
        returned.time_base = getattr(original, "time_base", None) or Fraction(1, returned.sample_rate)
        return returned

    async def encode(self, frame: MediaFrame, original: object) -> object:
        return await asyncio.to_thread(self._encode, frame, original)


@dataclass
class _ActiveSession:
    organization_id: str
    user_id: str
    expires_at: float
    peer: object
    worker_session: RunPodLiveSession

    async def close(self) -> None:
        try:
            await self.peer.close()
        finally:
            await self.worker_session.close()


class GatewayUnavailable(RuntimeError):
    pass


def _default_peer_factory(ice_servers: list[IceServer]) -> object:
    try:
        from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection
    except ImportError as exc:
        raise GatewayUnavailable("the aiortc media extra is not installed") from exc
    rtc_servers = [
        RTCIceServer(urls=item.urls, username=item.username, credential=item.credential)
        for item in ice_servers
    ]
    return RTCPeerConnection(RTCConfiguration(iceServers=rtc_servers))


def _default_description_factory(sdp: str, kind: str) -> object:
    try:
        from aiortc import RTCSessionDescription
    except ImportError as exc:
        raise GatewayUnavailable("the aiortc media extra is not installed") from exc
    return RTCSessionDescription(sdp=sdp, type=kind)


class LiveMediaGateway:
    """Authorize, connect, and own WebRTC/RunPod sessions in one process."""

    def __init__(
        self,
        settings: GatewaySettings,
        *,
        profile_authorizer: ProfileAuthorizer,
        worker_session_factory: WorkerSessionFactory | None = None,
        peer_factory: PeerFactory = _default_peer_factory,
        description_factory: Callable[[str, str], object] = _default_description_factory,
    ) -> None:
        self.settings = settings
        self.profile_authorizer = profile_authorizer
        self.worker_session_factory = worker_session_factory or self._connect_worker
        self.peer_factory = peer_factory
        self.description_factory = description_factory
        self._sessions: dict[str, _ActiveSession] = {}
        self._reservations: set[str] = set()
        self._lock = asyncio.Lock()

    def authenticate(self, authorization_header: str | None) -> bool:
        scheme, separator, supplied = (authorization_header or "").partition(" ")
        return separator == " " and scheme.lower() == "bearer" and hmac.compare_digest(
            supplied, self.settings.http_service_token
        )

    async def _connect_worker(self, **kwargs: Any) -> RunPodLiveSession:
        return await RunPodLiveSession.connect(
            host=self.settings.worker_host,
            port=self.settings.worker_port,
            service_token=self.settings.worker_service_token,
            ticket=kwargs["ticket"],
            session_id=kwargs["session_id"],
            face_profile_id=kwargs["face_profile_id"],
            voice_profile_id=kwargs["voice_profile_id"],
            region=self.settings.worker_region,
            ssl_context=ssl.create_default_context(),
            server_hostname=self.settings.worker_tls_server_name,
            max_inflight=self.settings.max_inflight,
        )

    async def create(self, request: CreateSessionRequest) -> GatewaySessionResponse:
        if request.consent_confirmed is not True:
            raise PermissionError("explicit face and voice authorization is required")
        if request.synthetic_media_indicator_enabled is not True:
            raise PermissionError("the synthetic-media indicator must remain enabled")
        authorized = self.profile_authorizer(
            request.organization_id, request.user_id,
            request.face_profile_id, request.voice_profile_id,
        )
        if hasattr(authorized, "__await__"):
            authorized = await authorized
        if (
            not isinstance(authorized, ProfileAuthorization)
            or authorized.face_profile_authorized is not True
            or authorized.voice_profile_authorized is not True
        ):
            raise PermissionError("both profiles must be authorized for this organization")

        session_id = uuid4().hex
        async with self._lock:
            if len(self._sessions) + len(self._reservations) >= self.settings.max_sessions:
                raise GatewayUnavailable("LiveShell session capacity is full")
            self._reservations.add(session_id)

        worker_session = None
        peer = None
        try:
            issued_at = int(time())
            ticket = issue_session_ticket(
                SessionTicketClaims(
                    organization_id=request.organization_id,
                    user_id=request.user_id,
                    session_id=session_id,
                    face_profile_id=request.face_profile_id,
                    voice_profile_id=request.voice_profile_id,
                    issued_at=issued_at,
                    expires_at=issued_at + MAX_TICKET_TTL_SECONDS,
                    face_consent_verified=True,
                    voice_consent_verified=True,
                    synthetic_media_indicator_enabled=True,
                ),
                self.settings.ticket_secret,
            )
            worker_session = await self.worker_session_factory(
                ticket=ticket,
                session_id=session_id,
                face_profile_id=request.face_profile_id,
                voice_profile_id=request.voice_profile_id,
            )
            client = getattr(worker_session, "client", None)
            if getattr(client, "require_realism_evidence", False) is not True:
                raise GatewayUnavailable("RunPod worker strict quality evidence is not enabled")
            accelerator = getattr(client, "actual_accelerator_profile", None)
            if accelerator not in SUPPORTED_ACCELERATOR_PROFILES or accelerator != request.target_accelerator_profile:
                raise GatewayUnavailable("RunPod worker did not attest the selected accelerator")

            peer = self.peer_factory(self.settings.ice_servers)
            metrics = _OutputMetrics()
            seen_tracks: set[str] = set()
            track_error: list[str] = []
            video_codec = _VideoCodec(metrics)
            audio_codec = _AudioCodec()

            def on_track(track: object) -> None:
                kind = getattr(track, "kind", None)
                if kind not in {"audio", "video"} or kind in seen_tracks:
                    track_error.append("offer must contain exactly one audio and one video track")
                    return
                seen_tracks.add(kind)
                try:
                    if kind == "video":
                        attach_video_track(
                            peer, track, worker_session.pipeline,
                            decode_frame=video_codec.decode,
                            encode_frame=video_codec.encode,
                            metadata_observer=metrics,
                        )
                    else:
                        attach_audio_track(
                            peer, track, worker_session.pipeline,
                            decode_frame=audio_codec.decode,
                            encode_frame=audio_codec.encode,
                            metadata_observer=metrics,
                        )
                except Exception:
                    track_error.append("offered media tracks could not be attached")

            peer.on("track", on_track)
            await peer.setRemoteDescription(
                self.description_factory(request.offer.sdp, "offer")
            )
            if track_error:
                raise ValueError(track_error[0])
            if seen_tracks != {"audio", "video"}:
                raise ValueError("offer must contain one camera and one microphone track")

            answer = await peer.createAnswer()
            await peer.setLocalDescription(answer)
            local = getattr(peer, "localDescription", None)
            if local is None:
                raise RuntimeError("WebRTC peer did not produce an answer")
            active = _ActiveSession(
                request.organization_id, request.user_id,
                monotonic() + self.settings.session_ttl_seconds, peer, worker_session,
            )
            async with self._lock:
                self._sessions[session_id] = active

            def on_connection_state_change() -> None:
                if getattr(peer, "connectionState", "") in {"failed", "closed"}:
                    asyncio.get_running_loop().create_task(self.close(session_id))

            peer.on("connectionstatechange", on_connection_state_change)
            return GatewaySessionResponse(
                session_id=session_id,
                answer=GatewayDescription(type="answer", sdp=local.sdp),
                face_profile_id=request.face_profile_id,
                voice_profile_id=request.voice_profile_id,
                face_profile_authorized=True,
                voice_profile_authorized=True,
                synthetic_media_indicator_enabled=True,
                runpod_session_connected=True,
                session_ticket_validated=True,
                realism_evidence_required=True,
                actual_accelerator_profile=accelerator,
            )
        except Exception:
            if peer is not None:
                try:
                    await peer.close()
                except Exception:
                    pass
            if worker_session is not None:
                try:
                    await worker_session.close()
                except Exception:
                    pass
            raise
        finally:
            async with self._lock:
                self._reservations.discard(session_id)

    async def close(
        self, session_id: str, *, organization_id: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        async with self._lock:
            active = self._sessions.get(session_id)
            if active is None:
                return False
            if organization_id is not None and active.organization_id != organization_id:
                return False
            if user_id is not None and active.user_id != user_id:
                return False
            self._sessions.pop(session_id, None)
        await active.close()
        return True

    async def close_expired(self) -> None:
        now = monotonic()
        async with self._lock:
            expired = [
                key for key, value in self._sessions.items() if value.expires_at <= now
            ]
        for session_id in expired:
            await self.close(session_id)


def _parse_ice_servers(raw: str) -> list[IceServer]:
    values = json.loads(raw)
    if not isinstance(values, list) or not values:
        raise ValueError("ICE server configuration must be a nonempty JSON array")
    result = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("each ICE server must be an object")
        urls = value.get("urls")
        if isinstance(urls, str):
            urls = [urls]
        if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
            raise ValueError("ICE server urls must be strings")
        username, credential = value.get("username"), value.get("credential")
        if username is not None and not isinstance(username, str):
            raise ValueError("ICE username must be a string")
        if credential is not None and not isinstance(credential, str):
            raise ValueError("ICE credential must be a string")
        result.append(IceServer(urls, username, credential))
    return result


def _load_profile_authorizer(spec: str) -> ProfileAuthorizer:
    module_name, separator, attribute_name = spec.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("SELDRUNE_PROFILE_AUTHORIZER must use module:function format")
    authorizer = getattr(importlib.import_module(module_name), attribute_name, None)
    if not callable(authorizer):
        raise ValueError("configured LiveShell profile authorizer is not callable")
    return authorizer


def gateway_from_environment() -> LiveMediaGateway:
    """Build the service only after trusted authorization and worker settings exist."""
    def setting(name: str) -> str:
        return os.getenv(name, "").strip()

    authorizer_spec = setting("SELDRUNE_PROFILE_AUTHORIZER")
    if not authorizer_spec:
        raise RuntimeError("SELDRUNE_PROFILE_AUTHORIZER is not configured")
    ice_raw = setting("SELDRUNE_LIVE_ICE_SERVERS_JSON")
    ice_servers = _parse_ice_servers(ice_raw) if ice_raw else [
        IceServer(["stun:stun.l.google.com:19302"])
    ]
    settings = GatewaySettings(
        http_service_token=setting("SELDRUNE_LIVESHIFT_WORKER_TOKEN"),
        worker_service_token=setting("SELDRUNE_LIVE_WORKER_TOKEN"),
        ticket_secret=setting("SELDRUNE_LIVE_TICKET_SECRET"),
        worker_host=setting("SELDRUNE_LIVE_WORKER_HOST"),
        worker_port=int(setting("SELDRUNE_LIVE_WORKER_PORT") or "8765"),
        worker_tls_server_name=setting("SELDRUNE_LIVE_WORKER_TLS_NAME")
        or setting("SELDRUNE_LIVE_WORKER_HOST"),
        worker_region=setting("SELDRUNE_LIVE_WORKER_REGION"),
        ice_servers=ice_servers,
        max_sessions=int(setting("SELDRUNE_LIVE_MAX_SESSIONS") or "1"),
        max_inflight=int(setting("SELDRUNE_LIVE_MAX_INFLIGHT") or "2"),
        session_ttl_seconds=int(setting("SELDRUNE_LIVE_SESSION_TTL_SECONDS") or "3600"),
    )
    return LiveMediaGateway(
        settings,
        profile_authorizer=_load_profile_authorizer(authorizer_spec),
    )


async def _cleanup_loop(gateway: LiveMediaGateway) -> None:
    while True:
        await asyncio.sleep(30)
        await gateway.close_expired()


def create_app(gateway: LiveMediaGateway | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = asyncio.create_task(_cleanup_loop(gateway)) if gateway is not None else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(title="Seldrune LiveShell WebRTC Gateway", lifespan=lifespan)
    app.state.gateway = gateway

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(request: Request) -> dict[str, object]:
        current = request.app.state.gateway
        if current is None:
            raise HTTPException(status_code=503, detail="LiveShell gateway is not configured")
        return {
            "status": "ready",
            "runpod_worker_configured": True,
            "profile_authorizer_configured": True,
            "strict_realism_evidence_required": True,
            "active_session_count": len(current._sessions),
            "max_sessions": current.settings.max_sessions,
        }

    @app.post(
        "/v1/sessions",
        status_code=status.HTTP_201_CREATED,
        response_model=GatewaySessionResponse,
    )
    async def create_session(
        payload: CreateSessionRequest, request: Request
    ) -> GatewaySessionResponse:
        current = request.app.state.gateway
        if current is None:
            raise HTTPException(status_code=503, detail="LiveShell gateway is not configured")
        if not current.authenticate(request.headers.get("authorization")):
            raise HTTPException(status_code=401, detail="Gateway authentication failed")
        try:
            return await current.create(payload)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except GatewayUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="LiveShell could not establish an authenticated media session.",
            ) from exc

    @app.delete("/v1/sessions/{session_id}")
    async def close_session(
        session_id: str,
        request: Request,
        organization_id: str,
        user_id: str,
    ) -> dict[str, bool]:
        current = request.app.state.gateway
        if current is None:
            raise HTTPException(status_code=503, detail="LiveShell gateway is not configured")
        if not current.authenticate(request.headers.get("authorization")):
            raise HTTPException(status_code=401, detail="Gateway authentication failed")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
            raise HTTPException(status_code=404, detail="LiveShell session not found")
        closed = await current.close(
            session_id, organization_id=organization_id, user_id=user_id
        )
        if not closed:
            raise HTTPException(status_code=404, detail="LiveShell session not found")
        return {"closed": True}

    return app


def _app_from_environment() -> FastAPI:
    try:
        return create_app(gateway_from_environment())
    except (ImportError, RuntimeError, TypeError, ValueError):
        return create_app()


app = _app_from_environment()
