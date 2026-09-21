"""External face-transformation provider adapter.

Keeps third-party inference behind a Seldrune-owned interface so providers can
be replaced without changing product-facing code. Use only with
authorized/consensual source and target media.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


class FaceProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class FaceSwapRequest:
    target_image: str
    source_face: str
    consent_confirmed: bool


class ReplicateFaceProvider:
    API = "https://api.replicate.com/v1/predictions"
    DEFAULT_VERSION = (
        "codeplugtech/face-swap:"
        "278a81e7ebb22db98bcba54de985d22cc1abeead2754eb1f2af717247be69b34"
    )

    def __init__(
        self,
        token: str | None = None,
        version: str | None = None,
        target_key: str | None = None,
        source_key: str | None = None,
    ) -> None:
        self.token = token or os.getenv("REPLICATE_API_TOKEN")
        self.version = version or os.getenv(
            "SELDRUNE_FACE_REPLICATE_VERSION", self.DEFAULT_VERSION
        )
        self.target_key = target_key or os.getenv(
            "SELDRUNE_FACE_TARGET_KEY", "input_image"
        )
        self.source_key = source_key or os.getenv(
            "SELDRUNE_FACE_SOURCE_KEY", "swap_image"
        )
        if not self.token:
            raise FaceProviderError("REPLICATE_API_TOKEN is not configured")

    def create(self, request: FaceSwapRequest) -> dict[str, Any]:
        if not request.consent_confirmed:
            raise FaceProviderError("consent confirmation is required")

        payload = {
            "version": self.version,
            "input": {
                self.target_key: request.target_image,
                self.source_key: request.source_face,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",
            "Cancel-After": "2m",
        }
        try:
            with httpx.Client(timeout=70.0) as client:
                response = client.post(self.API, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPError as exc:
            raise FaceProviderError("face provider request failed") from exc

        if result.get("status") in {"starting", "processing"}:
            result = self._poll_until_terminal(client_url=result.get("urls", {}).get("get"))

        if result.get("status") in {"failed", "canceled"}:
            raise FaceProviderError(result.get("error") or f"face provider {result.get('status')}")
        return result

    def _poll_until_terminal(self, client_url: str | None) -> dict[str, Any]:
        if not client_url:
            raise FaceProviderError("face provider did not return a prediction status URL")

        headers = {"Authorization": f"Bearer {self.token}"}
        deadline = time.monotonic() + 120.0
        try:
            with httpx.Client(timeout=20.0) as client:
                while time.monotonic() < deadline:
                    response = client.get(client_url, headers=headers)
                    response.raise_for_status()
                    result = response.json()
                    if result.get("status") in {"succeeded", "failed", "canceled"}:
                        return result
                    time.sleep(1.5)
        except httpx.HTTPError as exc:
            raise FaceProviderError("face provider status check failed") from exc

        raise FaceProviderError("face provider prediction timed out")
