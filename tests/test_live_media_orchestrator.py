import pytest
from services.live_media.contracts import ClientKind, TransformRequest
from services.live_media.orchestrator import build_session_plan
from services.live_media.policy import AuthorizationError

def test_mobile_thin_client_plan():
    p=build_session_plan(TransformRequest(session_id="s",user_id="u",client=ClientKind.ANDROID,face_profile_id="face",voice_profile_id="voice",consent_token="ok"))
    assert p.face_enabled and p.voice_enabled
    assert (p.width,p.height,p.fps)==(1280,720,30)
    assert p.synthetic_media_indicator

def test_consent_required():
    with pytest.raises(AuthorizationError):
        build_session_plan(TransformRequest(session_id="s",user_id="u",client=ClientKind.WEB,face_profile_id="face"))
