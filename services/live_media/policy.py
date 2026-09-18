from .contracts import TransformRequest

class AuthorizationError(ValueError):
    pass

def validate_transform_request(req: TransformRequest) -> None:
    if not req.face_profile_id and not req.voice_profile_id:
        raise AuthorizationError("At least one authorized transform profile is required")
    if not req.consent_token:
        raise AuthorizationError("Consent token is required for identity transformation")
    if req.capabilities.max_width < 1 or req.capabilities.max_height < 1:
        raise AuthorizationError("Invalid media capabilities")
