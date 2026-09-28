from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.live_media.runpod_facefusion_worker import (
    _authorize,
    _check_owner,
    app,
    build_facefusion_command,
    supports_video_dimensions,
)


def test_worker_command_pins_the_permissive_face_model_and_uses_argument_list():
    source = Path("/tmp/face;not-a-command.jpg")
    target = Path("/tmp/target video.mp4")
    output = Path("/tmp/output.mp4")

    command = build_facefusion_command(source, target, output)

    assert "ghost_1_256" in command
    assert "cuda" in command
    assert "--face-selector-mode" in command
    assert str(source) in command
    source_index = command.index("--source-paths")
    assert command[source_index + 1] == str(source)


def test_worker_authentication_fails_closed(monkeypatch):
    monkeypatch.delenv("SELDRUNE_FACESWAP_WORKER_TOKEN", raising=False)
    with pytest.raises(HTTPException) as not_configured:
        _authorize("Bearer anything")
    assert not_configured.value.status_code == 503

    monkeypatch.setenv("SELDRUNE_FACESWAP_WORKER_TOKEN", "expected-worker-token")
    with pytest.raises(HTTPException) as rejected:
        _authorize("Bearer wrong-token")
    assert rejected.value.status_code == 401
    _authorize("Bearer expected-worker-token")


def test_worker_job_endpoint_rejects_missing_auth_before_accepting_media(monkeypatch):
    monkeypatch.setenv("SELDRUNE_FACESWAP_WORKER_TOKEN", "expected-worker-token")
    client = TestClient(app)
    response = client.post(
        "/v1/jobs",
        data={
            "organization_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "00000000-0000-0000-0000-000000000002",
            "consent_confirmed": "true",
            "synthetic_media_indicator_enabled": "true",
        },
        files={
            "source_face": ("face.jpg", b"face", "image/jpeg"),
            "target_video": ("video.mp4", b"video", "video/mp4"),
        },
    )
    assert response.status_code == 401


def test_worker_job_is_bound_to_organization_and_user():
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"
    job = {"organization_id": org_id, "user_id": user_id}
    _check_owner(job, org_id, user_id)
    with pytest.raises(HTTPException) as rejected:
        _check_owner(job, "00000000-0000-0000-0000-000000000003", user_id)
    assert rejected.value.status_code == 404


def test_worker_accepts_portrait_1080p_and_rejects_larger_video():
    assert supports_video_dimensions(1080, 1920)
    assert supports_video_dimensions(1920, 1080)
    assert not supports_video_dimensions(1080, 2160)
    assert not supports_video_dimensions(3840, 2160)
