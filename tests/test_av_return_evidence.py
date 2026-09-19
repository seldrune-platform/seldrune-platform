from services.live_media.av_return_evidence import capture_av_return_evidence
from services.live_media.pipeline import LivePipeline
from services.live_media.processors import (
    PassthroughAudioProcessor,
    PassthroughVideoProcessor,
)


def make_pipeline():
    return LivePipeline(
        video=PassthroughVideoProcessor(),
        audio=PassthroughAudioProcessor(),
    )


def test_combined_av_evidence_passes_inside_drift_budget():
    pipeline = make_pipeline()
    pipeline.sync.video_ts_ms = 1000
    pipeline.sync.audio_ts_ms = 1040
    evidence = capture_av_return_evidence(
        pipeline, video_returned=True, audio_returned=True
    )
    assert evidence.verified is True
    assert evidence.drift_ms == 40
    assert evidence.correction == "none"
    assert evidence.as_receipt()["combined_av_return_verified"] is True


def test_combined_av_evidence_fails_outside_drift_budget():
    pipeline = make_pipeline()
    pipeline.sync.video_ts_ms = 1000
    pipeline.sync.audio_ts_ms = 1100
    evidence = capture_av_return_evidence(
        pipeline, video_returned=True, audio_returned=True
    )
    assert evidence.verified is False
    assert evidence.correction == "delay_video"


def test_combined_av_evidence_requires_both_tracks():
    pipeline = make_pipeline()
    pipeline.sync.video_ts_ms = 1000
    pipeline.sync.audio_ts_ms = 1000
    evidence = capture_av_return_evidence(
        pipeline, video_returned=True, audio_returned=False
    )
    assert evidence.verified is False
