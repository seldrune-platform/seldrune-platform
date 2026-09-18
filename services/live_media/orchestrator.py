from .contracts import SessionPlan, TransformRequest
from .policy import validate_transform_request

def build_session_plan(req: TransformRequest) -> SessionPlan:
    validate_transform_request(req)
    # Conservative baseline for mobile/ordinary laptops; cloud workers may negotiate upward.
    width=min(req.capabilities.max_width, 1280)
    height=min(req.capabilities.max_height, 720)
    fps=min(req.capabilities.max_fps, 30)
    return SessionPlan(
        face_enabled=bool(req.face_profile_id),
        voice_enabled=bool(req.voice_profile_id),
        width=width, height=height, fps=fps,
        synthetic_media_indicator=True,
    )
