import asyncio
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.api.routes.liveshell_mobile import (
    LiveSessionOffer,
    _effective_video_resolution,
    _parse_gateway_session,
    create_liveshell_live_session,
)


def valid_offer(**changes):
    values = {
        "offer": {"type": "offer", "sdp": "v=0\r\n" + ("candidate\r\n" * 5)},
        "face_profile_id": "approved-face-1",
        "voice_profile_id": "approved-voice-1",
        "consent_confirmed": True,
        "synthetic_media_indicator_enabled": True,
        "video_resolution": "1080p",
        "target_accelerator_profile": "rtx-4090",
    }
    values.update(changes)
    return LiveSessionOffer.model_validate(values)


def valid_gateway_response(**changes):
    values = {
        "session_id": "session_123",
        "answer": {"type": "answer", "sdp": "v=0\r\n" + ("candidate\r\n" * 5)},
        "face_profile_id": "approved-face-1",
        "voice_profile_id": "approved-voice-1",
        "face_profile_authorized": True,
        "voice_profile_authorized": True,
        "synthetic_media_indicator_enabled": True,
        "runpod_session_connected": True,
        "session_ticket_validated": True,
        "realism_evidence_required": True,
        "actual_accelerator_profile": "rtx-4090",
        "output_width": 1280,
        "output_height": 720,
        "audio_sample_rate_hz": 48000,
        "output_fps": 30,
    }
    values.update(changes)
    return values


def test_live_offer_accepts_4090_baseline_and_1080p_target():
    payload = valid_offer(video_resolution="1080p", target_accelerator_profile="rtx-4090")
    assert payload.video_resolution == "1080p"
    assert payload.target_accelerator_profile == "rtx-4090"


def test_live_offer_accepts_rtx_pro_4500_se_profile():
    payload = valid_offer(target_accelerator_profile="rtx-pro-4500-se")
    response = valid_gateway_response(actual_accelerator_profile="rtx-pro-4500-se")
    result = _parse_gateway_session(payload, response)
    assert payload.target_accelerator_profile == "rtx-pro-4500-se"
    assert result.actual_accelerator_profile == "rtx-pro-4500-se"


def test_live_offer_defaults_to_1080p30_for_hd():
    payload = valid_offer().model_dump(exclude={"video_resolution"})
    assert LiveSessionOffer.model_validate(payload).video_resolution == "1080p"


def test_live_offer_accepts_cloud_rtx_pro_6000_profile():
    payload = valid_offer(target_accelerator_profile="rtx-pro-6000-blackwell")
    response = valid_gateway_response(
        actual_accelerator_profile="rtx-pro-6000-blackwell"
    )
    result = _parse_gateway_session(payload, response)
    assert payload.target_accelerator_profile == "rtx-pro-6000-blackwell"
    assert result.actual_accelerator_profile == "rtx-pro-6000-blackwell"


def test_live_offer_rejects_unknown_gpu_target():
    with pytest.raises(ValidationError):
        valid_offer(target_accelerator_profile="rtx-4080")


def test_gateway_session_requires_matching_authorized_profiles():
    payload = valid_offer()
    result = _parse_gateway_session(payload, valid_gateway_response())
    assert result.face_profile_authorized
    assert result.voice_profile_authorized
    assert result.synthetic_media_indicator_enabled
    assert result.runpod_session_connected
    assert result.session_ticket_validated
    assert result.realism_evidence_required
    assert result.actual_accelerator_profile == "rtx-4090"
    assert _effective_video_resolution(result.output_width, result.output_height) == "720p"


@pytest.mark.parametrize(
    "changes",
    [
        {"face_profile_authorized": False},
        {"voice_profile_authorized": False},
        {"synthetic_media_indicator_enabled": False},
        {"runpod_session_connected": False},
        {"session_ticket_validated": False},
        {"realism_evidence_required": False},
        {"face_profile_id": "different-face"},
        {"voice_profile_id": "different-voice"},
    ],
)
def test_gateway_session_fails_closed_without_authorization_or_disclosure(changes):
    with pytest.raises(HTTPException) as error:
        _parse_gateway_session(valid_offer(), valid_gateway_response(**changes))
    assert error.value.status_code == 502


def test_unconfirmed_consent_is_rejected_before_gateway_call():
    from types import SimpleNamespace
    from uuid import uuid4

    payload = valid_offer(consent_confirmed=False)
    membership = SimpleNamespace(user_id=uuid4())
    with pytest.raises(HTTPException) as error:
        asyncio.run(create_liveshell_live_session(uuid4(), payload, membership))
    assert error.value.status_code == 422


def test_missing_synthetic_indicator_is_rejected_before_gateway_call():
    from types import SimpleNamespace
    from uuid import uuid4

    payload = valid_offer(synthetic_media_indicator_enabled=False)
    membership = SimpleNamespace(user_id=uuid4())
    with pytest.raises(HTTPException) as error:
        asyncio.run(create_liveshell_live_session(uuid4(), payload, membership))
    assert error.value.status_code == 422


def test_gateway_url_must_be_https_or_private(monkeypatch):
    from backend.app.api.routes.liveshell_mobile import _gateway_configuration

    monkeypatch.setenv("SELDRUNE_LIVESHIFT_WORKER_URL", "http://public.example")
    monkeypatch.setenv("SELDRUNE_LIVESHIFT_WORKER_TOKEN", "test-token")
    with pytest.raises(HTTPException) as error:
        _gateway_configuration()
    assert error.value.status_code == 503



def test_faceswap_worker_configuration_is_separate_from_live_gateway(monkeypatch):
    from backend.app.api.routes.liveshell_jobs import _faceswap_worker_configuration

    monkeypatch.setenv("SELDRUNE_LIVESHIFT_WORKER_URL", "https://live-gateway.example")
    monkeypatch.setenv("SELDRUNE_LIVESHIFT_WORKER_TOKEN", "live-token")
    monkeypatch.setenv("SELDRUNE_FACESWAP_WORKER_URL", "https://pod-8000.proxy.runpod.net")
    monkeypatch.setenv("SELDRUNE_FACESWAP_WORKER_TOKEN", "faceswap-token")

    assert _faceswap_worker_configuration() == (
        "https://pod-8000.proxy.runpod.net",
        "faceswap-token",
    )


def test_mobile_page_product_hub_and_assets_are_served():
    with TestClient(app) as client:
        page = client.get("/liveshell/mobile")
        faceswap_page = client.get("/liveshell/faceswap/mobile")
        products = client.get("/web/products.html")
        javascript = client.get("/console-assets/liveshell-mobile.js")
        stylesheet = client.get("/console-assets/liveshell-mobile.css")
        faceswap_javascript = client.get("/console-assets/liveshell-face-swap-mobile.js")

    assert page.status_code == 200
    assert "LIVESHELL · MOBILE STUDIO" in page.text
    assert 'value="rtx-pro-4500-se"' in page.text
    assert 'value="rtx-pro-6000-blackwell"' in page.text
    assert 'value="1080p" selected' in page.text
    assert faceswap_page.status_code == 200
    assert "Mobile FaceSwap" in faceswap_page.text
    assert products.status_code == 200
    assert 'href="/liveshell/mobile"' in products.text
    assert javascript.status_code == 200
    assert "output.measurement_status === 'measured'" in javascript.text
    assert "Awaiting first decoded frame" in javascript.text
    assert "Browser decoded " in javascript.text
    assert "FPS pending" in javascript.text
    assert stylesheet.status_code == 200
    assert faceswap_javascript.status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"audio_sample_rate_hz": 44_100},
        {"output_fps": 28.9},
        {"output_width": 640, "output_height": 480},
    ],
)
def test_gateway_rejects_unusable_media_metadata(changes):
    with pytest.raises(HTTPException) as error:
        _parse_gateway_session(valid_offer(), valid_gateway_response(**changes))
    assert error.value.status_code == 502


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (1920, 1080, "1080p"),
        (1080, 1920, "1080p"),
        (1280, 720, "720p"),
        (720, 1280, "720p"),
        (640, 480, None),
    ],
)
def test_gateway_resolution_is_orientation_neutral(width, height, expected):
    assert _effective_video_resolution(width, height) == expected


def test_gateway_response_marks_media_output_pending_until_first_frame():
    response = valid_gateway_response()
    for field in (
        "output_width",
        "output_height",
        "audio_sample_rate_hz",
        "output_fps",
    ):
        response.pop(field)

    result = _parse_gateway_session(valid_offer(), response)
    assert result.runpod_session_connected
    assert result.session_ticket_validated
    assert result.realism_evidence_required
    assert result.output_width is None
    assert result.output_height is None
    assert result.audio_sample_rate_hz is None
    assert result.output_fps is None
