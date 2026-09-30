"""Run the authenticated live A/V worker on a dedicated RunPod Pod."""

from __future__ import annotations

import asyncio
import importlib
import os
import ssl
from collections.abc import Awaitable, Callable

from .realism_quality_gate import RealismEvidenceError, RealismQualityPolicy
from .runpod_live_transport import RunPodLiveWorkerServer

Adapter = Callable[..., Awaitable[object]]


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        value = os.getenv(f"RUNPOD_SECRET_{name}", "").strip()
    if not value:
        raise RuntimeError(f"required live-worker setting is missing: {name}")
    return value


def _tls_material_path(
    value: str, name: str, open_fds: list[int]
) -> str:
    """Accept a mounted file path or keep inline PEM material in an anonymous file."""
    normalized = value.replace("\\n", "\n")
    if "-----BEGIN " not in normalized:
        return value
    memfd_create = getattr(os, "memfd_create", None)
    if memfd_create is None:
        raise RuntimeError("inline TLS PEM requires Linux anonymous-file support")
    fd = memfd_create(name, flags=0)
    try:
        remaining = memoryview(normalized.encode("utf-8"))
        while remaining:
            written = os.write(fd, remaining)
            if written <= 0:
                raise OSError("unable to write TLS material")
            remaining = remaining[written:]
        os.lseek(fd, 0, os.SEEK_SET)
    except Exception:
        os.close(fd)
        raise
    open_fds.append(fd)
    return f"/proc/self/fd/{fd}"


def _load_async_adapter(setting: str, name: str) -> Adapter:
    module_name, separator, attribute_name = setting.partition(":")
    if not separator or not module_name or not attribute_name:
        raise RuntimeError(f"{name} must use the module:callable format")
    module = importlib.import_module(module_name)
    adapter = getattr(module, attribute_name, None)
    if not callable(adapter) or not asyncio.iscoroutinefunction(adapter):
        raise RuntimeError(f"{name} must resolve to an async callable")
    return adapter




def _load_profile_preparer(setting: str, name: str) -> Adapter:
    """Require a sibling async prepare_profile hook for cold-start control."""
    module_name, separator, _ = setting.partition(":")
    if not separator or not module_name:
        raise RuntimeError(f"{name} must use the module:callable format")
    module = importlib.import_module(module_name)
    preparer = getattr(module, "prepare_profile", None)
    if not callable(preparer) or not asyncio.iscoroutinefunction(preparer):
        raise RuntimeError(f"{name} module must expose async prepare_profile")
    return preparer



def detect_actual_accelerator_profile() -> str:
    """Map the visible CUDA device to a supported profile; never trust a requested target."""
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required to attest the live GPU") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("a CUDA accelerator is required for LiveShell")
    name = torch.cuda.get_device_name(0).casefold()
    if "rtx pro 4500 se" in name:
        profile, minimum_gib = "rtx-pro-4500-se", 0.0
    elif "rtx pro 6000" in name and "blackwell" in name:
        profile, minimum_gib = "rtx-pro-6000-blackwell", 90.0
    elif "rtx 5090" in name:
        profile, minimum_gib = "rtx-5090", 31.5
    elif "rtx 4090" in name:
        profile, minimum_gib = "rtx-4090", 23.5
    else:
        raise RuntimeError("the visible CUDA device is not a supported LiveShell profile")
    total_gib = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    if total_gib < minimum_gib:
        raise RuntimeError("the visible CUDA device has less memory than its supported profile")
    return profile


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
    face_preparer = _load_profile_preparer(
        _required_setting("SELDRUNE_FACE_TRANSFORM_ADAPTER"),
        "SELDRUNE_FACE_TRANSFORM_ADAPTER",
    )
    voice_preparer = _load_profile_preparer(
        _required_setting("SELDRUNE_VOICE_TRANSFORM_ADAPTER"),
        "SELDRUNE_VOICE_TRANSFORM_ADAPTER",
    )
    video_labeler = _load_async_adapter(
        _required_setting("SELDRUNE_SYNTHETIC_VIDEO_LABELER"),
        "SELDRUNE_SYNTHETIC_VIDEO_LABELER",
    )
    face_evaluator = _load_async_adapter(
        _required_setting("SELDRUNE_FACE_QUALITY_EVALUATOR"),
        "SELDRUNE_FACE_QUALITY_EVALUATOR",
    )
    voice_evaluator = _load_async_adapter(
        _required_setting("SELDRUNE_VOICE_QUALITY_EVALUATOR"),
        "SELDRUNE_VOICE_QUALITY_EVALUATOR",
    )
    try:
        realism_policy = RealismQualityPolicy.from_json(
            _required_setting("SELDRUNE_LIVE_REALISM_POLICY_JSON")
        )
    except RealismEvidenceError as exc:
        raise RuntimeError("SELDRUNE_LIVE_REALISM_POLICY_JSON is invalid") from exc

    tls_secret_fds: list[int] = []
    cert_value = _required_setting("SELDRUNE_LIVE_TLS_CERT")
    key_value = _required_setting("SELDRUNE_LIVE_TLS_KEY")
    cert_path = _tls_material_path(
        cert_value, "seldrune-live-tls-cert", tls_secret_fds
    )
    key_path = _tls_material_path(
        key_value, "seldrune-live-tls-key", tls_secret_fds
    )
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        tls.load_cert_chain(certfile=cert_path, keyfile=key_path)
    finally:
        for fd in tls_secret_fds:
            os.close(fd)

    try:
        port = int(os.getenv("SELDRUNE_LIVE_WORKER_PORT", "8765"))
    except ValueError as exc:
        raise RuntimeError("SELDRUNE_LIVE_WORKER_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("SELDRUNE_LIVE_WORKER_PORT is outside the valid range")

    actual_accelerator_profile = detect_actual_accelerator_profile()
    worker = RunPodLiveWorkerServer(
        service_token=service_token,
        actual_accelerator_profile=actual_accelerator_profile,
        ticket_secret=ticket_secret,
        transform_face=face_transform,
        transform_voice=voice_transform,
        label_synthetic_video=video_labeler,
        evaluate_face=face_evaluator,
        evaluate_voice=voice_evaluator,
        prepare_face_profile=face_preparer,
        prepare_voice_profile=voice_preparer,
        realism_policy=realism_policy,
        require_realism_evidence=True,
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
