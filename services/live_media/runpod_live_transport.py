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
import inspect
import json
import math
import secrets
import ssl
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter, time
from typing import Any
from uuid import uuid4

from .realism_quality_gate import (
    FaceTransformOutput,
    RealismQualityPolicy,
    VoiceTransformOutput,
    validate_face_realism,
    validate_voice_realism,
)
from .avsync import AVSyncState
from .realism_quality_gate import RealismEvidenceError
from .worker_protocol import InferenceRequest, InferenceResult, MediaKind

MAX_HEADER_BYTES = 4096
MAX_VIDEO_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_AUDIO_PAYLOAD_BYTES = 512 * 1024
MAX_TICKET_TTL_SECONDS = 900
AUDIENCE = "seldrune-live-media"
SUPPORTED_ACCELERATOR_PROFILES = frozenset({
    "rtx-4090",
    "rtx-pro-4500-se",
    "rtx-5090",
    "rtx-pro-6000-blackwell",
})

Transform = Callable[..., Awaitable[bytes | FaceTransformOutput | VoiceTransformOutput]]
VideoLabeler = Callable[[bytes], Awaitable[bytes]]


async def _invoke_transform(
    adapter: Transform,
    payload: bytes,
    profile_id: str,
    metadata: dict[str, Any],
) -> bytes | FaceTransformOutput | VoiceTransformOutput:
    """Pass validated frame metadata to adapters that declare that parameter."""
    try:
        parameters = inspect.signature(adapter).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "media_metadata" in parameters:
        return await adapter(payload, profile_id, media_metadata=metadata)
    if "metadata" in parameters:
        return await adapter(payload, profile_id, metadata=metadata)
    positional = [
        parameter
        for parameter in parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(
        parameter.kind is inspect.Parameter.VAR_POSITIONAL
        for parameter in parameters.values()
    )
    if len(positional) >= 3 or has_varargs:
        return await adapter(payload, profile_id, metadata)
    return await adapter(payload, profile_id)


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
        pixel_format = header.get("pixel_format")
        valid_dimensions = type(width) is int and type(height) is int
        long_edge = max(width, height) if valid_dimensions else 0
        short_edge = min(width, height) if valid_dimensions else 0
        valid_fps = type(fps) in (int, float) and math.isfinite(float(fps))
        if (
            not valid_dimensions
            or not valid_fps
            or short_edge < 720
            or long_edge < 1280
            or fps < 24
            or fps > 60
            or short_edge > 2160
            or long_edge > 3840
            or pixel_format not in (None, "jpeg", "rgb24")
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
        realism_policy: RealismQualityPolicy | None = None,
        require_realism_evidence: bool = False,
        actual_accelerator_profile: str | None = None,
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
        if require_realism_evidence and realism_policy is None:
            raise ValueError("strict live realism evidence requires a quality policy")
        self.max_sessions = max_sessions
        self.max_inflight_per_connection = max_inflight_per_connection
        self.realism_policy = realism_policy
        self.require_realism_evidence = require_realism_evidence
        if (
            actual_accelerator_profile is not None
            and actual_accelerator_profile not in SUPPORTED_ACCELERATOR_PROFILES
        ):
            raise ValueError("unsupported actual accelerator profile")
        self.actual_accelerator_profile = actual_accelerator_profile
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
            ready_header: dict[str, Any] = {
                "type": "ready",
                "session_id": claims.session_id,
                "video_profile": "hd-720p30-minimum",
                "audio_sample_rate_hz": 48000,
                "synthetic_video_label_required": True,
                "realism_evidence_required": self.require_realism_evidence,
            }
            if self.actual_accelerator_profile is not None:
                ready_header["actual_accelerator_profile"] = (
                    self.actual_accelerator_profile
                )
            await write_message(writer, ready_header)

            last_sequence: dict[str, int] = {}
            inflight_ids: set[str] = set()
            av_sync = AVSyncState()
            saw_audio_timestamp = False
            saw_video_timestamp = False
            av_sync_by_request: dict[str, dict[str, int | float]] = {}

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
                    quality_evidence: dict[str, Any] | None = None
                    media_metadata = {
                        key: header.get(key)
                        for key in (
                            "width", "height", "fps", "sample_rate_hz", "channels", "pixel_format"
                        )
                    }
                    if kind == MediaKind.VIDEO:
                        model_output = await _invoke_transform(
                            self.transform_face, payload, profile_id, media_metadata
                        )
                        if isinstance(model_output, FaceTransformOutput):
                            if self.realism_policy is None:
                                raise RuntimeError("face quality policy is not configured")
                            transformed = model_output.payload
                            quality_evidence = validate_face_realism(
                                model_output.evidence, self.realism_policy
                            )
                        elif isinstance(model_output, bytes) and not self.require_realism_evidence:
                            transformed = model_output
                        else:
                            raise RuntimeError("face adapter must return measured realism evidence")
                        if not isinstance(transformed, bytes) or not transformed:
                            raise RuntimeError("face transform returned no output")
                        transformed = await self.label_synthetic_video(transformed)
                    else:
                        model_output = await _invoke_transform(
                            self.transform_voice, payload, profile_id, media_metadata
                        )
                        if isinstance(model_output, VoiceTransformOutput):
                            if self.realism_policy is None:
                                raise RuntimeError("voice quality policy is not configured")
                            transformed = model_output.payload
                            quality_evidence = validate_voice_realism(
                                model_output.evidence, self.realism_policy
                            )
                        elif isinstance(model_output, bytes) and not self.require_realism_evidence:
                            transformed = model_output
                        else:
                            raise RuntimeError(
                                "voice adapter must return measured realism evidence"
                            )
                        if not isinstance(transformed, bytes) or not transformed:
                            raise RuntimeError("voice transform returned no output")
                    if not isinstance(transformed, bytes) or not transformed:
                        raise RuntimeError("media transform returned no output")
                    inference_ms = max((perf_counter() - started) * 1000, 0.001)
                    if (
                        self.require_realism_evidence
                        and self.realism_policy is not None
                        and inference_ms > self.realism_policy.max_processing_p95_ms
                    ):
                        raise RuntimeError("live transform exceeded the processing latency limit")
                    response = {
                        "type": "result",
                        "request_id": request_id,
                        "session_id": claims.session_id,
                        "media_kind": str(kind),
                        "timestamp_ms": timestamp_ms,
                        "sequence": header["sequence"],
                        "inference_ms": inference_ms,
                        "synthetic_label_applied": kind == MediaKind.VIDEO,
                        "sample_rate_hz": header.get("sample_rate_hz"),
                        "channels": header.get("channels"),
                        "width": header.get("width"),
                        "height": header.get("height"),
                        "fps": header.get("fps"),
                        "pixel_format": header.get("pixel_format"),
                    }
                    if quality_evidence is not None:
                        if kind == MediaKind.VIDEO:
                            response["width"] = quality_evidence.get(
                                "output_width", response["width"]
                            )
                            response["height"] = quality_evidence.get(
                                "output_height", response["height"]
                            )
                            response["fps"] = quality_evidence.get(
                                "output_fps", response["fps"]
                            )
                        else:
                            response["sample_rate_hz"] = quality_evidence.get(
                                "sample_rate_hz", response["sample_rate_hz"]
                            )
                            response["channels"] = quality_evidence.get(
                                "channels", response["channels"]
                            )
                        quality_evidence["transport_inference_ms"] = inference_ms
                        paired_sync = av_sync_by_request.get(request_id)
                        if paired_sync is not None:
                            quality_evidence["av_sync"] = paired_sync
                        response["realism_evidence"] = quality_evidence
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
                    av_sync_by_request.pop(request_id, None)

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
                if self.require_realism_evidence and self.realism_policy is not None:
                    if kind == MediaKind.AUDIO:
                        av_sync.audio_ts_ms = message.header["timestamp_ms"]
                        saw_audio_timestamp = True
                    else:
                        av_sync.video_ts_ms = message.header["timestamp_ms"]
                        saw_video_timestamp = True
                    if saw_audio_timestamp and saw_video_timestamp:
                        try:
                            av_sync_by_request[request_id] = av_sync.validate_realism(
                                self.realism_policy
                            )
                        except RealismEvidenceError:
                            await send(
                                {
                                    "type": "error",
                                    "request_id": request_id,
                                    "code": "av_sync_threshold_exceeded",
                                }
                            )
                            continue
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
        require_realism_evidence: bool = False,
        actual_accelerator_profile: str | None = None,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.session_id = session_id
        self.require_realism_evidence = require_realism_evidence
        self.actual_accelerator_profile = actual_accelerator_profile
        self._write_lock = asyncio.Lock()
        if max_inflight < 1:
            raise ValueError("at least one in-flight media request is required")
        self._slots = asyncio.Semaphore(max_inflight)
        self._pending: dict[str, asyncio.Future[InferenceResult]] = {}
        self._expected: dict[str, tuple[MediaKind, int]] = {}
        self._expected_pixel_format: dict[str, str | None] = {}
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
        if (
            ssl_context is None
            or ssl_context.verify_mode == ssl.CERT_NONE
            or not ssl_context.check_hostname
        ):
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
        actual_accelerator_profile = ready.header.get("actual_accelerator_profile")
        if actual_accelerator_profile is not None and (
            not isinstance(actual_accelerator_profile, str)
            or actual_accelerator_profile not in SUPPORTED_ACCELERATOR_PROFILES
        ):
            writer.close()
            await writer.wait_closed()
            raise StreamProtocolError("RunPod worker reported an unsupported accelerator")
        return cls(
            reader,
            writer,
            session_id=session_id,
            max_inflight=max_inflight,
            require_realism_evidence=(
                ready.header.get("realism_evidence_required") is True
            ),
            actual_accelerator_profile=actual_accelerator_profile,
        )

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
                expected_pixel_format = self._expected_pixel_format[request_id]
                if (
                    header.get("type") != "result"
                    or header.get("session_id") != self.session_id
                    or header.get("media_kind") != str(expected_kind)
                    or header.get("timestamp_ms") != expected_timestamp
                    or header.get("pixel_format") != expected_pixel_format
                    or (
                        header.get("synthetic_label_applied") is not True
                        and header.get("media_kind") == MediaKind.VIDEO
                    )
                ):
                    future.set_exception(StreamProtocolError("invalid worker result"))
                    continue
                quality_evidence = header.get("realism_evidence")
                if (
                    (quality_evidence is not None and not isinstance(quality_evidence, dict))
                    or (self.require_realism_evidence and not isinstance(quality_evidence, dict))
                    or (
                        isinstance(quality_evidence, dict)
                        and quality_evidence.get("media_kind") != str(expected_kind)
                    )
                ):
                    future.set_exception(StreamProtocolError("missing or invalid realism evidence"))
                    continue
                if not message.payload:
                    future.set_exception(
                        StreamProtocolError("worker returned an empty result")
                    )
                    continue
                is_video = header.get("media_kind") == "video"
                width = header.get("width")
                height = header.get("height")
                fps = header.get("fps")
                sample_rate_hz = header.get("sample_rate_hz")
                channels = header.get("channels")
                future.set_result(
                    InferenceResult(
                        request_id=request_id,
                        timestamp_ms=int(header["timestamp_ms"]),
                        payload=message.payload,
                        inference_ms=float(header["inference_ms"]),
                        quality_evidence=quality_evidence,
                        width=width if is_video and type(width) is int else None,
                        height=height if is_video and type(height) is int else None,
                        fps=(
                            float(fps)
                            if is_video
                            and type(fps) in (int, float)
                            and math.isfinite(float(fps))
                            else None
                        ),
                        sample_rate_hz=(
                            sample_rate_hz
                            if not is_video and type(sample_rate_hz) is int
                            else None
                        ),
                        channels=(
                            channels if not is_video and type(channels) is int else None
                        ),
                        pixel_format=(
                            header.get("pixel_format")
                            if is_video and isinstance(header.get("pixel_format"), str)
                            else None
                        ),
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
        if kind == MediaKind.VIDEO and request.pixel_format not in (None, "jpeg", "rgb24"):
            self._slots.release()
            raise StreamProtocolError("unsupported video pixel format")
        if kind == MediaKind.AUDIO and request.pixel_format is not None:
            self._slots.release()
            raise StreamProtocolError("audio requests cannot declare a video pixel format")
        if request.request_id in self._pending:
            self._slots.release()
            raise StreamProtocolError("duplicate in-flight request id")
        future: asyncio.Future[InferenceResult] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[request.request_id] = future
        self._expected[request.request_id] = (kind, request.timestamp_ms)
        self._expected_pixel_format[request.request_id] = request.pixel_format
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
            if request.pixel_format is not None:
                header["pixel_format"] = request.pixel_format
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
            self._expected_pixel_format.pop(request.request_id, None)
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
