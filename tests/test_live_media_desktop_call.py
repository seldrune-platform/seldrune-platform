import pytest

from clients.desktop.call_mode import DesktopCallMode
from clients.desktop.privacy import ScreenSharePolicy


def test_default_call_mode_is_safe():
    mode = DesktopCallMode()
    mode.activate()
    assert mode.screen_share.selected_window_only
    assert not mode.screen_share.allow_ui_spoofing
    assert not mode.screen_share.allow_capture_bypass


def test_stealth_capture_bypass_rejected():
    policy = ScreenSharePolicy(allow_capture_bypass=True)
    with pytest.raises(ValueError):
        policy.validate()


def test_ui_spoofing_rejected():
    policy = ScreenSharePolicy(allow_ui_spoofing=True)
    with pytest.raises(ValueError):
        policy.validate()
