from services.live_media.quality import NetworkSample, choose_quality
from services.live_media.telemetry import SessionMetrics

def test_quality_degrades_on_bad_network():
    q=choose_quality(NetworkSample(300,.10,500))
    assert (q.width,q.height,q.fps)==(640,360,24)

def test_quality_720p_on_good_network():
    q=choose_quality(NetworkSample(40,.005,5000))
    assert (q.width,q.height,q.fps)==(1280,720,30)

def test_metrics_average():
    m=SessionMetrics(); m.record_inference(10); m.record_inference(20)
    assert m.average_inference_ms==15
