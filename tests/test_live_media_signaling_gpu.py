import pytest

from services.live_media.gpu_runtime import (
    GPUCapabilities,
    GPUHealth,
    RuntimeKind,
    can_accept,
)
from services.live_media.signaling import SignalingSession, SignalState


def test_signaling_flow():
    session = SignalingSession("s", "u")
    session.set_offer("offer")
    session.set_answer("answer")
    assert session.state == SignalState.CONNECTED


def test_answer_before_offer_rejected():
    with pytest.raises(ValueError):
        SignalingSession("s", "u").set_answer("answer")


def test_gpu_capacity():
    capabilities = GPUCapabilities("gpu", 24000, RuntimeKind.CUDA)
    assert can_accept(capabilities, GPUHealth(0.4, 8000, 60, True))
    assert not can_accept(capabilities, GPUHealth(0.95, 8000, 60, True))
