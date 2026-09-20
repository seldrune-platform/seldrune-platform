"""Tests for client-side WebRTC receiver observations."""

from fractions import Fraction

import pytest

from services.live_media.receiver_observation import ReceiverObservationRecorder


class _VideoFrame:
    width = 1280
    height = 720
    time_base = Fraction(1, 90000)

    def __init__(self, pts: int) -> None:
        self.pts = pts


class _AudioFrame:
    sample_rate = 48000
    time_base = Fraction(1, 48000)

    def __init__(self, pts: int) -> None:
        self.pts = pts


def test_receiver_records_video_count_and_latest_metadata():
    recorder = ReceiverObservationRecorder()

    recorder.record_video(_VideoFrame(0))
    latest = recorder.record_video(_VideoFrame(3000))

    assert recorder.video_frames == 2
    assert recorder.latest_video == latest
    assert latest.width == 1280
    assert latest.height == 720
    assert latest.timestamp_ms == pytest.approx(1000 / 30)


def test_receiver_derives_audio_duration_from_received_timestamps():
    recorder = ReceiverObservationRecorder()

    recorder.record_audio(_AudioFrame(0))
    recorder.record_audio(_AudioFrame(960))
    recorder.record_audio(_AudioFrame(1920))

    assert recorder.audio_duration_seconds == pytest.approx(0.04)
    assert recorder.latest_audio.sample_rate_hz == 48000


def test_single_audio_frame_has_zero_observed_duration():
    recorder = ReceiverObservationRecorder()

    recorder.record_audio(_AudioFrame(0))

    assert recorder.audio_duration_seconds == 0.0


def test_receiver_rejects_non_increasing_audio_timestamps():
    recorder = ReceiverObservationRecorder()
    recorder.record_audio(_AudioFrame(960))

    with pytest.raises(ValueError, match="timestamps must increase"):
        recorder.record_audio(_AudioFrame(960))


def test_receiver_records_client_video_latency_p95():
    recorder = ReceiverObservationRecorder()

    for latency_ms in (10.0, 20.0, 30.0, 40.0, 50.0):
        recorder.record_video_return_latency(latency_ms)

    assert recorder.p95_video_return_latency_ms == pytest.approx(50.0)


def test_receiver_has_no_client_latency_before_measurement():
    recorder = ReceiverObservationRecorder()

    assert recorder.p95_video_return_latency_ms is None


@pytest.mark.parametrize("latency_ms", [0.0, -1.0, float("inf"), float("nan")])
def test_receiver_rejects_invalid_client_video_latency(latency_ms):
    recorder = ReceiverObservationRecorder()

    with pytest.raises(ValueError, match="client-received video latency must be positive"):
        recorder.record_video_return_latency(latency_ms)
