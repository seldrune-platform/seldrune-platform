"""Authenticated, bounded audio/video transport for a RunPod live worker.

This module is the TCP media boundary only. Seldrune's trusted gateway issues
the short-lived session ticket after checking organization permissions, enrolled
profile authorization, and explicit face/voice consent. Production listeners
must use TLS. Concrete GPU model adapters are injected and must be ready before
the listener is started.
"""

from __future__ import annotations

import asyncio
import base64
import hmac
import json
import secrets
import ssl
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter, time
from typing import Any
from uuid import uuid4

from .worker_protocol import InferenceRequest, InferenceResult, MediaKind

MAX_HEADER_BYTES = 4096
MAX_VIDEO_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_AUDIO_PAYLOAD_BYTES = 512 * 1024
MAX_TICKET_TTL_SECONDS = 900
AUDIENCE = "seldrune-live-media"

Transform = Callable[[bytes, str], Awaitable[bytes]]
VideoLabeler = Callable[[bytes], Awaitable[bytes]]


class StreamProtocolError(ValueError):
    """A malformed or unauthorized live-worker message."""


@dataclass(frozen=True)
class SessionTicketClaims:
    organization_id: str
    user_id: str
    session_id: str
    face_profile_id: str
    voice_profile_id: str
    issued_at: int
    expires_at: int
    face_consent_verified: bool
    voice_consent_verified: bool
    synthetic_media_indicator_enabled: bool
    audience: str = AUDIENCE
    ticket_id: str = ""


@dataclass(frozen=True)
class StreamMessage:
    header: dict[str, Any]
    payload: bytes


def _secret_bytes(secret: str | bytes) -> bytes:
    value = secret.encode("utf-8") if isinstance(secret, str) else secret
    if len(value) < 32:
        raise ValueError("live-worker signing secrets must be at least 32 bytes")
    return value


def _ticket_payload(claims: SessionTicketClaims) -> dict[str, Any]:
    return {
        "aud": claims.audience,
        "exp": claims.expires_at,
        "face_consent_verified": claims.face_consent_verified,
        "face_profile_id": claims.face_profile_id,
        "iat": claims.issued_at,
        "jti": claims.ticket_id,
        "organization_id": claims.organization_id,
        "session_id": claims.session_id,
        "synthetic_media_indicator_enabled": claims.synthetic_media_indicator_enabled,
        "user_id": claims.user_id,
        "voice_consent_verified": claims.voice_consent_verified,
        "voice_profile_id": claims.voice_profile_id,
    }


def _validate_claim_payload(payload: object, *, now: int) -> SessionTicketClaims:
    if not isinstance(payload, dict):
        raise StreamProtocolError("invalid session ticket")
    string_fields = (
        "organization_id",
        "user_id",
        "session_id",
        "face_profile_id",
        "voice_profile_id",
    )
    if any(
        not isinstance(payload.get(field), str)
        or not payload[field]
        or len(payload[field]) > 128
        for field in string_fields
    ):
        raise StreamProtocolError("invalid session ticket claims")
    ticket_id = payload.get("jti")
    if not isinstance(ticket_id, str) or not ticket_id or len(ticket_id) > 80:
        raise StreamProtocolError("invalid session ticket id")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    if type(issued_at) is not int or type(expires_at) is not int:
        raise StreamProtocolError("invalid session ticket lifetime")
    if issued_at > now + 30 or expires_at <= now:
        raise StreamProtocolError("session ticket expired or not yet valid")
    if expires_at <= issued_at or expires_at - issued_at > MAX_TICKET_TTL_SECONDS:
        raise StreamProtocolError("session ticket lifetime is not allowed")
    if payload.get("aud") != AUDIENCE:
        raise StreamProtocolError("invalid session ticket audience")
    if (
        payload.get("face_consent_verified") is not True
        or payload.get("voice_consent_verified") is not True
        or payload.get("synthetic_media_indicator_enabled") is not True
    ):
        raise StreamProtocolError(
            "verified face, voice, and disclosure consent required"
        )
    return SessionTicketClaims(
        organization_id=payload["organization_id"],
        user_id=payload["user_id"],
        session_id=payload["session_id"],
        face_profile_id=payload["face_profile_id"],
        voice_profile_id=payload["voice_profile_id"],
        issued_at=issued_at,
        expires_at=expires_at,
        face_consent_verified=True,
        voice_consent_verified=True,
        synthetic_media_indicator_enabled=True,
        ticket_id=ticket_id,
    )


def issue_session_ticket(
    claims: SessionTicketClaims, signing_secret: str | bytes
) -> str:
    """Sign server-verified claims for a single, short-lived live session."""
    now = int(time())
    payload = _ticket_payload(claims)
    payload["jti"] = claims.ticket_id or uuid4().hex
    _validate_claim_payload(payload, now=now)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=")
    signature = hmac.digest(_secret_bytes(signing_secret), encoded, "sha256")
    signature_text = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded.decode('ascii')}.{signature_text}"


def verify_session_ticket(
    ticket: str, signing_secret: str | bytes, *, now: int | None = None
) -> SessionTicketClaims:
    parts = ticket.split(".") if isinstance(ticket, str) else []
    if len(parts) != 2:
        raise StreamProtocolError("invalid session ticket")
    encoded, signature_text = parts
    try:
        signature = base64.urlsafe_b64decode(
            signature_text + "=" * (-len(signature_text) % 4)
        )
        payload_bytes = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError) as exc:
        raise StreamProtocolError("invalid session ticket") from exc
    expected = hmac.digest(
        _secret_bytes(signing_secret), encoded.encode("ascii"), "sha256"
    )
    if not hmac.compare_digest(signature, expected):
        raise StreamProtocolError("invalid session ticket signature")
    return _validate_claim_payload(payload, now=int(time()) if now is None else now)


def _payload_limit(header: dict[str, Any]) -> int:
    kind = header.get("media_kind")
    if kind == MediaKind.VIDEO:
        return MAX_VIDEO_PAYLOAD_BYTES
    if kind == MediaKind.AUDIO:
        return MAX_AUDIO_PAYLOAD_BYTES
    return 0


def encode_message(header: dict[str, Any], payload: bytes = b"") -> bytes:
    """Encode one bounded JSON-header plus binary-payload message."""
    if not isinstance(payload, bytes):
        raise StreamProtocolError("media payload must be bytes")
    if len(payload) > _payload_limit(header):
        raise StreamProtocolError("media payload exceeds the allowed size")
    message_header = dict(header)
    message_header["payload_bytes"] = len(payload)
    header_bytes = json.dumps(
        message_header, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if not header_bytes or len(header_bytes) > MAX_HEADER_BYTES:
        raise StreamProtocolError("message header exceeds the allowed size")
    return struct.pack("!I", len(header_bytes)) + header_bytes + payload


async def write_message(
    writer: asyncio.StreamWriter, header: dict[str, Any], payload: bytes = b""
) -> None:
    writer.write(encode_message(header, payload))
    await writer.drain()


async def read_message(reader: asyncio.StreamReader) -> StreamMessage:
    header_size = struct.unpack("!I", await reader.readexactly(4))[0]
    if not 0 < header_size <= MAX_HEADER_BYTES:
        raise StreamProtocolError("invalid message header size")
    try:
        header = json.loads(await reader.readexactly(header_size))
    except (ValueError, json.JSONDecodeError) as exc:
        raise StreamProtocolError("invalid message header") from exc
    if not isinstance(header, dict):
        raise StreamProtocolError("message header must be an object")
    payload_size = header.get("payload_bytes")
    if type(payload_size) is not int or payload_size < 0:
        raise StreamProtocolError("invalid media payload size")
    if payload_size > _payload_limit(header):
        raise StreamProtocolError("media payload exceeds the allowed size")
    return StreamMessage(header, await reader.readexactly(payload_size))


def _validate_media_request(
    header: dict[str, Any],
    payload: bytes,
    claims: SessionTicketClaims,
    last_sequence: dict[str, int],
) -> tuple[MediaKind, str, int, int]:
    if header.get("type") != "request" or header.get("session_id") != claims.session_id:
        raise StreamProtocolError("request is not bound to this live session")
    request_id = header.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 80:
        raise StreamProtocolError("invalid request id")
    try:
        kind = MediaKind(header.get("media_kind"))
    except ValueError as exc:
        raise StreamProtocolError("unsupported media kind") from exc
    expected_profile = (
        claims.face_profile_id if kind == MediaKind.VIDEO else claims.voice_profile_id
    )
    profile_id = header.get("profile_id")
    if not isinstance(profile_id, str) or not secrets.compare_digest(
        profile_id, expected_profile
    ):
        raise StreamProtocolError("profile is not authorized for this media track")
    sequence = header.get("sequence")
    timestamp_ms = header.get("timestamp_ms")
    if (
        type(sequence) is not int
        or sequence < 0
        or type(timestamp_ms) is not int
        or timestamp_ms < 0
    ):
        raise StreamProtocolError("invalid media timing metadata")
    if sequence <= last_sequence.get(str(kind), -1):
        raise StreamProtocolError("stale or repeated media sequence")
    if not payload:
        raise StreamProtocolError("empty media payload")
    if kind == MediaKind.VIDEO:
        width = header.get("width")
        height = header.get("height")
        fps = header.get("fps")
        if (
            type(width) is not int
            or type(height) is not int
            or type(fps) is not int
            or width < 1280
            or height < 720
            or fps < 24
            or fps > 60
            or width > 3840
            or height > 2160
        ):
            raise StreamProtocolError("video does not meet the supported HD profile")
    else:
        sample_rate = header.get("sample_rate_hz")
        channels = header.get("channels")
        if (
            type(sample_rate) is not int
            or sample_rate < 48000
            or type(channels) is not int
            or channels not in (1, 2)
        ):
            raise StreamProtocolError(
                "audio does not meet the supported 48 kHz profile"
            )
    last_sequence[str(kind)] = sequence
    return kind, request_id, timestamp_ms, sequence


class RunPodLiveWorkerServer:
    """TLS TCP worker that transforms authorized video and voice packets."""

    def __init__(
        self,
        *,
        service_token: str,
        ticket_secret: str | bytes,
        transform_face: Transform,
        transform_voice: Transform,
        label_synthetic_video: VideoLabeler,
        max_sessions: int = 1,
        max_inflight_per_connection: int = 2,
    ) -> None:
        _secret_bytes(service_token)
        _secret_bytes(ticket_secret)
        if max_sessions < 1:
            raise ValueError("at least one live session slot is required")
        if max_inflight_per_connection < 1:
            raise ValueError("at least one in-flight media request is required")
        if not all(
            callable(adapter)
            for adapter in (transform_face, transform_voice, label_synthetic_video)
        ):
            raise ValueError("face, voice, and synthetic-label adapters are required")
        self.service_token = service_token
        self.ticket_secret = ticket_secret
        self.transform_face = transform_face
        self.transform_voice = transform_voice
        self.label_synthetic_video = label_synthetic_video
        self.max_sessions = max_sessions
        self.max_inflight_per_connection = max_inflight_per_connection
        self._used_tickets: dict[str, int] = {}
        self._active_sessions: set[str] = set()

    async def serve(
        self, host: str, port: int, *, ssl_context: ssl.SSLContext | None
    ) -> asyncio.AbstractServer:
        if ssl_context is None:
            raise ValueError("RunPod live media must use TLS")
        return await asyncio.start_server(
            self.handle, host, port, ssl=ssl_context, limit=MAX_HEADER_BYTES + 4
        )

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        inflight: set[asyncio.Task[None]] = set()
        write_lock = asyncio.Lock()
        registered_session: str | None = None
        try:
            hello_message = await read_message(reader)
            hello = hello_message.header
            if hello.get("type") != "hello" or hello_message.payload:
                raise StreamProtocolError("live session handshake required")
            supplied_token = hello.get("service_token")
            if not isinstance(supplied_token, str) or not hmac.compare_digest(
                supplied_token, self.service_token
            ):
                await write_message(
                    writer, {"type": "error", "code": "authentication_failed"}
                )
                return
            claims = verify_session_ticket(hello.get("ticket", ""), self.ticket_secret)
            if hello.get("session_id") != claims.session_id:
                raise StreamProtocolError(
                    "session ticket does not match the connection"
                )
            now = int(time())
            self._used_tickets = {
                ticket_id: expiry
                for ticket_id, expiry in self._used_tickets.items()
                if expiry > now
            }
            if claims.ticket_id in self._used_tickets:
                raise StreamProtocolError("session ticket has already been used")
            if claims.session_id in self._active_sessions:
                await write_message(
                    writer, {"type": "error", "code": "session_already_active"}
                )
                return
            if len(self._active_sessions) >= self.max_sessions:
                await write_message(
                    writer, {"type": "error", "code": "worker_capacity_exceeded"}
                )
                return
            self._used_tickets[claims.ticket_id] = claims.expires_at
            self._active_sessions.add(claims.session_id)
            registered_session = claims.session_id
            await write_message(
                writer,
                {
                    "type": "ready",
                    "session_id": claims.session_id,
                    "video_profile": "hd-720p30-minimum",
                    "audio_sample_rate_hz": 48000,
                    "synthetic_video_label_required": True,
                },
            )

            last_sequence: dict[str, int] = {}
            inflight_ids: set[str] = set()

            async def send(header: dict[str, Any], payload: bytes = b"") -> None:
                async with write_lock:
                    await write_message(writer, header, payload)

            async def process(header: dict[str, Any], payload: bytes) -> None:
                request_id = str(header.get("request_id", ""))
                try:
                    kind = MediaKind(header["media_kind"])
                    profile_id = str(header["profile_id"])
                    timestamp_ms = int(header["timestamp_ms"])
                    started = perf_counter()
                    if kind == MediaKind.VIDEO:
                        transformed = await self.transform_face(payload, profile_id)
                        transformed = await self.label_synthetic_video(transformed)
                    else:
                        transformed = await self.transform_voice(payload, profile_id)
                    if not isinstance(transformed, bytes) or not transformed:
                        raise RuntimeError("media transform returned no output")
                    response = {
                        "type": "result",
                        "request_id": request_id,
                        "session_id": claims.session_id,
                        "media_kind": str(kind),
                        "timestamp_ms": timestamp_ms,
                        "sequence": header["sequence"],
                        "inference_ms": max((perf_counter() - started) * 1000, 0.001),
                        "synthetic_label_applied": kind == MediaKind.VIDEO,
                        "sample_rate_hz": header.get("sample_rate_hz"),
                        "width": header.get("width"),
                        "height": header.get("height"),
                        "fps": header.get("fps"),
                    }
                    await send(response, transformed)
                except Exception:
                    await send(
                        {
                            "type": "error",
                            "request_id": request_id,
                            "code": "media_processing_failed",
                        }
                    )
                finally:
                    inflight_ids.discard(request_id)

            while True:
                message = await read_message(reader)
                kind, request_id, _, _ = _validate_media_request(
                    message.header, message.payload, claims, last_sequence
                )
                if request_id in inflight_ids:
                    raise StreamProtocolError("duplicate in-flight request id")
                if len(inflight) >= self.max_inflight_per_connection:
                    await send(
                        {
                            "type": "error",
                            "request_id": request_id,
                            "code": "worker_busy",
                        }
                    )
                    continue
                # The selected profile is validated above before any model code runs.
                if kind not in (MediaKind.VIDEO, MediaKind.AUDIO):
                    raise StreamProtocolError("unsupported media kind")
                inflight_ids.add(request_id)
                task = asyncio.create_task(process(message.header, message.payload))
                inflight.add(task)
                task.add_done_callback(inflight.discard)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        except StreamProtocolError:
            try:
                async with write_lock:
                    await write_message(
                        writer, {"type": "error", "code": "invalid_live_request"}
                    )
            except (ConnectionError, OSError):
                pass
        finally:
            for task in inflight:
                task.cancel()
            if inflight:
                await asyncio.gather(*inflight, return_exceptions=True)
            if registered_session is not None:
                self._active_sessions.discard(registered_session)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass


class RunPodLiveWorkerClient:
    """Multiplexed TLS client; bounds pending work to avoid stale-frame queues."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        session_id: str,
        max_inflight: int = 2,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.session_id = session_id
        self._write_lock = asyncio.Lock()
        if max_inflight < 1:
            raise ValueError("at least one in-flight media request is required")
        self._slots = asyncio.Semaphore(max_inflight)
        self._pending: dict[str, asyncio.Future[InferenceResult]] = {}
        self._expected: dict[str, tuple[MediaKind, int]] = {}
        self._next_sequence = {str(MediaKind.VIDEO): 0, str(MediaKind.AUDIO): 0}
        self._closed = False
        self._reader_task = asyncio.create_task(self._read_results())

    @classmethod
    async def connect(
        cls,
        host: str,
        port: int,
        *,
        service_token: str,
        ticket: str,
        session_id: str,
        ssl_context: ssl.SSLContext,
        server_hostname: str,
        max_inflight: int = 2,
    ) -> RunPodLiveWorkerClient:
        if ssl_context is None or ssl_context.verify_mode == ssl.CERT_NONE:
            raise ValueError("RunPod live media requires verified TLS")
        reader, writer = await asyncio.open_connection(
            host, port, ssl=ssl_context, server_hostname=server_hostname
        )
        await write_message(
            writer,
            {
                "type": "hello",
                "service_token": service_token,
                "ticket": ticket,
                "session_id": session_id,
            },
        )
        try:
            ready = await asyncio.wait_for(read_message(reader), timeout=5.0)
        except Exception:
            writer.close()
            await writer.wait_closed()
            raise
        if (
            ready.header.get("type") != "ready"
            or ready.header.get("session_id") != session_id
            or ready.header.get("synthetic_video_label_required") is not True
        ):
            writer.close()
            await writer.wait_closed()
            raise StreamProtocolError("RunPod worker did not admit the live session")
        return cls(reader, writer, session_id=session_id, max_inflight=max_inflight)

    async def _read_results(self) -> None:
        try:
            while True:
                message = await read_message(self.reader)
                request_id = message.header.get("request_id")
                future = (
                    self._pending.get(request_id)
                    if isinstance(request_id, str)
                    else None
                )
                if future is None or future.done():
                    continue
                if message.header.get("type") == "error":
                    future.set_exception(
                        RuntimeError(str(message.header.get("code", "worker_error")))
                    )
                    continue
                header = message.header
                expected_kind, expected_timestamp = self._expected[request_id]
                if (
                    header.get("type") != "result"
                    or header.get("session_id") != self.session_id
                    or header.get("media_kind") != str(expected_kind)
                    or header.get("timestamp_ms") != expected_timestamp
                    or (
                        header.get("synthetic_label_applied") is not True
                        and header.get("media_kind") == MediaKind.VIDEO
                    )
                ):
                    future.set_exception(StreamProtocolError("invalid worker result"))
                    continue
                if not message.payload:
                    future.set_exception(
                        StreamProtocolError("worker returned an empty result")
                    )
                    continue
                future.set_result(
                    InferenceResult(
                        request_id=request_id,
                        timestamp_ms=int(header["timestamp_ms"]),
                        payload=message.payload,
                        inference_ms=float(header["inference_ms"]),
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            for future in tuple(self._pending.values()):
                if not future.done():
                    future.set_exception(
                        RuntimeError("RunPod live worker connection lost")
                    )
            self._closed = True
            if not self.writer.is_closing():
                self.writer.close()

    async def infer(
        self,
        request: InferenceRequest,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        sample_rate_hz: int = 48000,
        channels: int = 1,
        timeout_s: float = 2.0,
    ) -> InferenceResult:
        if self._closed:
            raise RuntimeError("RunPod live worker connection is closed")
        if request.session_id != self.session_id:
            raise StreamProtocolError("request belongs to another live session")
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=0.03)
        except TimeoutError as exc:
            raise RuntimeError(
                "live worker is busy; stale media was not queued"
            ) from exc
        kind = MediaKind(request.media_kind)
        if request.request_id in self._pending:
            self._slots.release()
            raise StreamProtocolError("duplicate in-flight request id")
        future: asyncio.Future[InferenceResult] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[request.request_id] = future
        self._expected[request.request_id] = (kind, request.timestamp_ms)
        header: dict[str, Any] = {
            "type": "request",
            "request_id": request.request_id,
            "session_id": request.session_id,
            "media_kind": str(kind),
            "profile_id": request.profile_id,
            "timestamp_ms": request.timestamp_ms,
        }
        if kind == MediaKind.VIDEO:
            header.update(
                width=request.width or width,
                height=request.height or height,
                fps=request.fps or fps,
            )
        else:
            header.update(
                sample_rate_hz=request.sample_rate_hz or sample_rate_hz,
                channels=request.channels or channels,
            )
        try:
            async with self._write_lock:
                kind_key = str(kind)
                sequence = max(request.sequence, self._next_sequence[kind_key])
                self._next_sequence[kind_key] = sequence + 1
                header["sequence"] = sequence
                await write_message(self.writer, header, request.payload)
            return await asyncio.wait_for(future, timeout=timeout_s)
        finally:
            self._pending.pop(request.request_id, None)
            self._expected.pop(request.request_id, None)
            self._slots.release()

    async def __call__(
        self, _worker: object, request: InferenceRequest
    ) -> InferenceResult:
        """Use a session-scoped connection as the WorkerPool inference callback."""
        return await self.infer(request)

    async def close(self) -> None:
        self._closed = True
        if not self._reader_task.done():
            self._reader_task.cancel()
        await asyncio.gather(self._reader_task, return_exceptions=True)
        for future in self._pending.values():
            if not future.done():
                future.set_exception(RuntimeError("live worker session closed"))
        if not self.writer.is_closing():
            self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass
