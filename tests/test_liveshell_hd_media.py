import pytest

from services.liveshell.hd_media import (
    HDVideoTarget,
    HDVoiceTarget,
    LiveShellRuntimeEvidence,
)


def test_hd_targets_validate():
    HDVideoTarget().validate()
    HDVoiceTarget().validate()


def test_sub_hd_video_is_rejected():
    with pytest.raises(ValueError, match="1280x720"):
        HDVideoTarget(width=640, height=480).validate()


def test_mobile_ready_requires_all_runtime_evidence():
    partial = LiveShellRuntimeEvidence(
        hd_video_returned=True,
        hd_audio_returned=True,
        av_sync_verified=True,
    )
    assert partial.hd_mobile_ready is False

    verified = LiveShellRuntimeEvidence(
        hd_video_returned=True,
        hd_audio_returned=True,
        av_sync_verified=True,
        mobile_session_verified=True,
    )
    assert verified.hd_mobile_ready is True
