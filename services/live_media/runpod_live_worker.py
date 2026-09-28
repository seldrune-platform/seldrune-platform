"""Run the authenticated live A/V worker on a dedicated RunPod Pod."""

from __future__ import annotations

import asyncio
import importlib
import os
import ssl
from collections.abc import Awaitable, Callable

from .runpod_live_transport import RunPodLiveWorkerServer

Adapter = Callable[..., Awaitable[bytes]]


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"required live-worker setting is missing: {name}")
    return value


def _load_async_adapter(setting: str, name: str) -> Adapter:
    module_name, separator, attribute_name = setting.partition(":")
    if not separator or not module_name or not attribute_name:
        raise RuntimeError(f"{name} must use the module:callable format")
    module = importlib.import_module(module_name)
    adapter = getattr(module, attribute_name, None)
    if not callable(adapter) or not asyncio.iscoroutinefunction(adapter):
        raise RuntimeError(f"{name} must resolve to an async callable")
    return adapter


def worker_from_environment() -> tuple[
    RunPodLiveWorkerServer, ssl.SSLContext, str, int
]:
    """Load model adapters and TLS material without logging any secret values."""
    service_token = _required_setting("SELDRUNE_LIVE_WORKER_TOKEN")
    ticket_secret = _required_setting("SELDRUNE_LIVE_TICKET_SECRET")
    face_transform = _load_async_adapter(
        _required_setting("SELDRUNE_FACE_TRANSFORM_ADAPTER"),
        "SELDRUNE_FACE_TRANSFORM_ADAPTER",
    )
    voice_transform = _load_async_adapter(
        _required_setting("SELDRUNE_VOICE_TRANSFORM_ADAPTER"),
        "SELDRUNE_VOICE_TRANSFORM_ADAPTER",
    )
    video_labeler = _load_async_adapter(
        _required_setting("SELDRUNE_SYNTHETIC_VIDEO_LABELER"),
        "SELDRUNE_SYNTHETIC_VIDEO_LABELER",
    )

    cert_path = _required_setting("SELDRUNE_LIVE_TLS_CERT")
    key_path = _required_setting("SELDRUNE_LIVE_TLS_KEY")
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(certfile=cert_path, keyfile=key_path)

    try:
        port = int(os.getenv("SELDRUNE_LIVE_WORKER_PORT", "8765"))
    except ValueError as exc:
        raise RuntimeError("SELDRUNE_LIVE_WORKER_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("SELDRUNE_LIVE_WORKER_PORT is outside the valid range")

    worker = RunPodLiveWorkerServer(
        service_token=service_token,
        ticket_secret=ticket_secret,
        transform_face=face_transform,
        transform_voice=voice_transform,
        label_synthetic_video=video_labeler,
        max_sessions=int(os.getenv("SELDRUNE_LIVE_MAX_SESSIONS", "1")),
        max_inflight_per_connection=int(
            os.getenv("SELDRUNE_LIVE_MAX_INFLIGHT", "2")
        ),
    )
    return worker, tls, os.getenv("SELDRUNE_LIVE_WORKER_HOST", "0.0.0.0"), port


async def serve() -> None:
    worker, tls, host, port = worker_from_environment()
    server = await worker.serve(host, port, ssl_context=tls)
    async with server:
        await server.serve_forever()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
