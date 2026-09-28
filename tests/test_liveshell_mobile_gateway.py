import asyncio
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.api.routes.liveshell_mobile import (
    LiveSessionOffer,
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
        "video_resolution": "720p",
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


def test_live_offer_rejects_unknown_gpu_target():
    with pytest.raises(ValidationError):
        valid_offer(target_accelerator_profile="rtx-4080")


def test_gateway_session_requires_matching_authorized_profiles():
    payload = valid_offer()
    result = _parse_gateway_session(payload, valid_gateway_response())
    assert result.face_profile_authorized
    assert result.voice_profile_authorized
    assert result.synthetic_media_indicator_enabled
    assert result.actual_accelerator_profile == "rtx-4090"


@pytest.mark.parametrize(
    "changes",
    [
        {"face_profile_authorized": False},
        {"voice_profile_authorized": False},
        {"synthetic_media_indicator_enabled": False},
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
    assert "<title>Live video</title>" in page.text
    assert "Seldrune" not in page.text
    assert "SELDRUNE" not in page.text
    assert "LiveShell" not in page.text
    assert "Start session" in page.text
    assert "AI modified" in page.text
    assert faceswap_page.status_code == 200
    assert "Mobile FaceSwap" in faceswap_page.text
    assert products.status_code == 200
    assert 'href="/liveshell/mobile"' in products.text
    assert javascript.status_code == 200
    assert stylesheet.status_code == 200
    assert faceswap_javascript.status_code == 200
