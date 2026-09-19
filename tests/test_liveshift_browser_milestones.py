from services.live_media.milestones import ProductMilestones


def _base(**overrides):
    values = dict(
        webrtc_runtime=True,
        gpu_runtime=True,
        face_model_loaded=True,
        first_frame_transformed=True,
        live_stream_returned=True,
    )
    values.update(overrides)
    return ProductMilestones(**values)


def test_browser_readiness_does_not_require_virtual_camera():
    milestones = _base(browser_live_session_verified=True)
    assert milestones.browser_live_ready is True
    assert milestones.desktop_virtual_camera_ready is False
    assert milestones.meeting_call_ready is False


def test_desktop_camera_readiness_requires_real_camera_evidence():
    milestones = _base(
        browser_live_session_verified=True,
        virtual_camera_connected=True,
    )
    assert milestones.browser_live_ready is True
    assert milestones.desktop_virtual_camera_ready is True
    assert milestones.meeting_call_ready is True


def test_webrtc_return_alone_is_not_browser_session_evidence():
    milestones = _base(browser_live_session_verified=False)
    assert milestones.browser_live_ready is False
