from services.live_media.quality import NetworkSample, choose_quality
from services.live_media.telemetry import SessionMetrics


def test_quality_degrades_on_bad_network():
    quality = choose_quality(NetworkSample(300, 0.10, 500))
    assert (quality.width, quality.height, quality.fps) == (640, 360, 24)


def test_quality_720p_on_good_network():
    quality = choose_quality(NetworkSample(40, 0.005, 5000))
    assert (quality.width, quality.height, quality.fps) == (1280, 720, 30)


def test_metrics_average():
    metrics = SessionMetrics()
    metrics.record_inference(10)
    metrics.record_inference(20)
    assert metrics.average_inference_ms == 15
