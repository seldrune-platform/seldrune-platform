import pytest
from services.live_media.signaling import SignalingSession,SignalState
from services.live_media.gpu_runtime import GPUCapabilities,GPUHealth,RuntimeKind,can_accept

def test_signaling_flow():
    s=SignalingSession("s","u"); s.set_offer("offer"); s.set_answer("answer")
    assert s.state==SignalState.CONNECTED

def test_answer_before_offer_rejected():
    with pytest.raises(ValueError): SignalingSession("s","u").set_answer("answer")

def test_gpu_capacity():
    c=GPUCapabilities("gpu",24000,RuntimeKind.CUDA)
    assert can_accept(c,GPUHealth(.4,8000,60,True))
    assert not can_accept(c,GPUHealth(.95,8000,60,True))
