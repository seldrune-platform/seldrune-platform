"""Runtime milestone reporting based on capabilities, not architecture claims."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProductMilestones:
    webrtc_runtime: bool = False
    gpu_runtime: bool = False
    face_model_loaded: bool = False
    first_frame_transformed: bool = False
    live_stream_returned: bool = False
    browser_live_session_verified: bool = False
    virtual_camera_connected: bool = False

    @property
    def first_visible_output_ready(self) -> bool:
        return (
            self.webrtc_runtime
            and self.gpu_runtime
            and self.face_model_loaded
            and self.first_frame_transformed
        )

    @property
    def browser_live_ready(self) -> bool:
        return (
            self.first_visible_output_ready
            and self.live_stream_returned
            and self.browser_live_session_verified
        )

    @property
    def desktop_virtual_camera_ready(self) -> bool:
        return self.browser_live_ready and self.virtual_camera_connected

    @property
    def meeting_call_ready(self) -> bool:
        """Backward-compatible desktop virtual-camera milestone."""
        return self.desktop_virtual_camera_ready
