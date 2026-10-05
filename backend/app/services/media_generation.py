from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

import httpx


OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"


@dataclass(frozen=True)
class GeneratedMedia:
    data: bytes
    mime_type: str
    model: str


class MediaGenerationError(RuntimeError):
    """A provider failure that can be reported without exposing credentials."""


def _provider_error(status_code: int) -> MediaGenerationError:
    if status_code in {401, 403}:
        message = "OpenAI rejected the saved credential. Reconnect OpenAI in Seldrune Connections."
    elif status_code == 429:
        message = "OpenAI rate limits or account quota blocked this request."
    elif status_code == 400:
        message = "OpenAI rejected this media request. Revise the prompt and try again."
    elif status_code >= 500:
        message = "OpenAI's media service is temporarily unavailable."
    else:
        message = f"OpenAI could not complete the media request (HTTP {status_code})."
    return MediaGenerationError(message)


def generate_image(
    prompt: str,
    *,
    api_key: str,
    model: str = "gpt-image-2",
    quality: str = "low",
    size: str = "1024x1024",
) -> GeneratedMedia:
    try:
        response = httpx.post(
            OPENAI_IMAGES_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "prompt": prompt,
                "quality": quality,
                "size": size,
                "n": 1,
                "output_format": "png",
            },
            timeout=180.0,
        )
    except httpx.RequestError as exc:
        raise MediaGenerationError("Could not reach OpenAI's image service.") from exc
    if response.status_code >= 400:
        raise _provider_error(response.status_code)
    try:
        payload = response.json()
        encoded = payload["data"][0]["b64_json"]
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("empty image")
        image = base64.b64decode(encoded, validate=True)
    except (KeyError, IndexError, TypeError, ValueError, binascii.Error) as exc:
        raise MediaGenerationError("OpenAI returned an unreadable image response.") from exc
    if not image:
        raise MediaGenerationError("OpenAI returned an empty image.")
    if len(image) > 20 * 1024 * 1024:
        raise MediaGenerationError("OpenAI returned an image larger than Seldrune accepts.")
    return GeneratedMedia(data=image, mime_type="image/png", model=model)


def generate_speech(
    text: str,
    *,
    api_key: str,
    model: str = "gpt-4o-mini-tts",
    voice: str = "marin",
) -> GeneratedMedia:
    try:
        response = httpx.post(
            OPENAI_SPEECH_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": "mp3",
            },
            timeout=120.0,
        )
    except httpx.RequestError as exc:
        raise MediaGenerationError("Could not reach OpenAI's speech service.") from exc
    if response.status_code >= 400:
        raise _provider_error(response.status_code)
    audio = response.content
    if not audio:
        raise MediaGenerationError("OpenAI returned an empty audio file.")
    if len(audio) > 20 * 1024 * 1024:
        raise MediaGenerationError("OpenAI returned audio larger than Seldrune accepts.")
    return GeneratedMedia(data=audio, mime_type="audio/mpeg", model=model)
