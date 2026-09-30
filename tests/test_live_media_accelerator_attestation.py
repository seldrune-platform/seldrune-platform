import asyncio
import sys
from types import SimpleNamespace

import pytest

from services.live_media.runpod_live_transport import _invoke_transform
from services.live_media import runpod_live_worker as worker_module
from services.live_media.runpod_live_worker import detect_actual_accelerator_profile


def test_live_adapter_receives_frame_metadata_and_two_argument_adapters_still_work():
    async def scenario():
        received = {}

        async def metadata_adapter(payload, profile_id, *, media_metadata):
            received.update(media_metadata)
            return payload + profile_id.encode()

        async def legacy_adapter(payload, profile_id):
            return payload + profile_id.encode()

        metadata = {
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "sample_rate_hz": None,
            "channels": None,
        }
        output = await _invoke_transform(
            metadata_adapter, b"rgb", "face-1", metadata
        )
        legacy = await _invoke_transform(legacy_adapter, b"pcm", "voice-1", {})
        assert output == b"rgbface-1"
        assert received == metadata
        assert legacy == b"pcmvoice-1"

    asyncio.run(scenario())


def test_actual_accelerator_profile_comes_from_cuda_device(monkeypatch):
    cuda = SimpleNamespace(
        is_available=lambda: True,
        get_device_name=lambda _index: "NVIDIA GeForce RTX 4090",
        get_device_properties=lambda _index: SimpleNamespace(
            total_memory=24 * 1024**3
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    assert detect_actual_accelerator_profile() == "rtx-4090"


def test_unknown_or_missing_cuda_hardware_is_not_advertised(monkeypatch):
    cuda = SimpleNamespace(
        is_available=lambda: True,
        get_device_name=lambda _index: "NVIDIA GeForce RTX 4080",
        get_device_properties=lambda _index: SimpleNamespace(
            total_memory=16 * 1024**3
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    with pytest.raises(RuntimeError, match="not a supported"):
        detect_actual_accelerator_profile()

    cuda.is_available = lambda: False
    with pytest.raises(RuntimeError, match="CUDA accelerator"):
        detect_actual_accelerator_profile()



def test_worker_reads_runpod_secret_prefix_with_direct_env_precedence(monkeypatch):
    name = "SELDRUNE_LIVE_WORKER_TOKEN"
    monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(f"RUNPOD_SECRET_{name}", "  runpod-secret  ")
    assert worker_module._required_setting(name) == "runpod-secret"

    monkeypatch.setenv(name, "direct-value")
    assert worker_module._required_setting(name) == "direct-value"


def test_inline_tls_pem_is_opened_from_anonymous_file():
    if not hasattr(worker_module.os, "memfd_create"):
        pytest.skip("Linux anonymous files are required")
    fds = []
    pem = "-----BEGIN CERTIFICATE-----\\nYWJj\\n-----END CERTIFICATE-----"
    path = worker_module._tls_material_path(pem, "test-cert", fds)
    try:
        with open(path, encoding="utf-8") as handle:
            assert handle.read() == (
                "-----BEGIN CERTIFICATE-----\\nYWJj\\n-----END CERTIFICATE-----"
            ).replace("\\n", "\n")
    finally:
        for fd in fds:
            worker_module.os.close(fd)
