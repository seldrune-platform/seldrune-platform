"""Meeting-app agnostic desktop call-mode configuration."""
from dataclasses import dataclass

from .privacy import PresentationMode, ScreenSharePolicy


@dataclass
class DesktopCallMode:
    camera_name: str = "Seldrune Live Camera"
    microphone_name: str = "Seldrune Live Microphone"
    presentation: PresentationMode = PresentationMode.MEETING_FOCUS
    screen_share: ScreenSharePolicy = ScreenSharePolicy()

    def activate(self) -> None:
        self.screen_share.validate()
