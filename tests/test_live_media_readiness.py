from services.live_media.gpu_backend_runtime import GPUBackendStatus
from services.live_media.readiness import LiveMediaReadiness
from services.live_media.webrtc_runtime import WebRTCRuntimeStatus


def test_readiness_requires_webrtc_and_gpu():
    ready = LiveMediaReadiness(
        WebRTCRuntimeStatus("aiortc", True, "ok"),
        GPUBackendStatus(True, False, False),
    )
    assert ready.production_ready

    no_gpu = LiveMediaReadiness(
        WebRTCRuntimeStatus("aiortc", True, "ok"),
        GPUBackendStatus(False, False, False),
    )
    assert not no_gpu.production_ready

    no_webrtc = LiveMediaReadiness(
        WebRTCRuntimeStatus("none", False, "missing"),
        GPUBackendStatus(True, False, False),
    )
    assert not no_webrtc.production_ready
