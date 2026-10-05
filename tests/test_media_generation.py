import base64

import pytest

from backend.app.services import media_generation


class FakeResponse:
    def __init__(self, *, status_code=200, content=b"", payload=None):
        self.status_code = status_code
        self.content = content
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_image_generation_returns_png_bytes_and_uses_server_key(monkeypatch):
    image = b"png image bytes"
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(
            payload={"data": [{"b64_json": base64.b64encode(image).decode("ascii")}]}
        )

    monkeypatch.setattr(media_generation.httpx, "post", fake_post)
    result = media_generation.generate_image(
        "A blue mountain under the moon",
        api_key="secret-test-key",
    )

    assert result.data == image
    assert result.mime_type == "image/png"
    assert result.model == "gpt-image-2"
    assert captured["url"] == media_generation.OPENAI_IMAGES_URL
    assert captured["headers"] == {"Authorization": "Bearer secret-test-key"}
    assert captured["json"]["prompt"] == "A blue mountain under the moon"
    assert captured["json"]["output_format"] == "png"


def test_speech_generation_returns_mp3_and_selects_disclosed_voice(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(content=b"mp3 audio bytes")

    monkeypatch.setattr(media_generation.httpx, "post", fake_post)
    result = media_generation.generate_speech(
        "Welcome to Seldrune.",
        api_key="secret-test-key",
    )

    assert result.data == b"mp3 audio bytes"
    assert result.mime_type == "audio/mpeg"
    assert result.model == "gpt-4o-mini-tts"
    assert captured["url"] == media_generation.OPENAI_SPEECH_URL
    assert captured["json"]["voice"] == "marin"
    assert captured["json"]["response_format"] == "mp3"


def test_media_generation_reports_provider_quota_failure_without_credentials(monkeypatch):
    monkeypatch.setattr(
        media_generation.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(status_code=429),
    )

    with pytest.raises(media_generation.MediaGenerationError, match="rate limits"):
        media_generation.generate_speech("Hello.", api_key="secret-test-key")

