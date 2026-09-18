"""Desktop presentation policy for Seldrune Live.

The client may minimize controls and guide users to share a selected meeting
window. It must not spoof another application's UI or bypass OS/app capture.
"""
from dataclasses import dataclass
from enum import StrEnum


class PresentationMode(StrEnum):
    NORMAL = "normal"
    TRAY = "tray"
    MEETING_FOCUS = "meeting_focus"


@dataclass(frozen=True)
class ScreenSharePolicy:
    selected_window_only: bool = True
    allow_ui_spoofing: bool = False
    allow_capture_bypass: bool = False

    def validate(self) -> None:
        if self.allow_ui_spoofing or self.allow_capture_bypass:
            raise ValueError("stealth presentation behavior is not supported")
