import pytest

from services.live_media.transport_metadata import (
    DeliveredAudioMetadata,
    DeliveredVideoMetadata,
)


def test_delivered_video_metadata_requires_positive_dimensions():
    assert DeliveredVideoMetadata(1280, 720).width == 1280
    with pytest.raises(ValueError, match="dimensions must be positive"):
        DeliveredVideoMetadata(0, 720)


def test_delivered_audio_metadata_requires_positive_sample_rate():
    assert DeliveredAudioMetadata(48000).sample_rate_hz == 48000
    with pytest.raises(ValueError, match="sample rate must be positive"):
        DeliveredAudioMetadata(0)
