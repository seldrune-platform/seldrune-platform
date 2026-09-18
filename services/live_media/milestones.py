"""Runtime milestone reporting based on capabilities, not architecture claims."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProductMilestones:
    webrtc_runtime: bool = False
    gpu_runtime: bool = False
    face_model_loaded: bool = False
    first_frame_transformed: bool = False
    live_stream_returned: bool = False
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
    def meeting_call_ready(self) -> bool:
        return (
            self.first_visible_output_ready
            and self.live_stream_returned
            and self.virtual_camera_connected
        )
